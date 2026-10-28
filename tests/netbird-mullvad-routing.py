#!/usr/bin/env python3
"""Kernel regression helper: run only inside an isolated user/network namespace."""

import errno
import importlib.util
import json
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = "198.51.100.10"
PUBLIC_HTTPS = "93.184.216.34"
FW_MARK = "0x6d6f6c65"


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def echo_peer():
    print("namespace-ready", flush=True)
    input()
    for args in (
        ("link", "set", "lo", "up"),
        ("addr", "add", "100.64.0.2/16", "dev", "mesh-peer"),
        ("addr", "add", f"{GATEWAY}/32", "dev", "mesh-peer"),
        ("addr", "add", f"{PUBLIC_HTTPS}/32", "dev", "mesh-peer"),
        ("link", "set", "mesh-peer", "up"),
        ("route", "add", "default", "via", "100.64.0.1"),
    ):
        run("ip", *args)

    class Echo(socketserver.BaseRequestHandler):
        def handle(self):
            while packet := self.request.recv(4096):
                self.request.sendall(packet)

    server = socketserver.ThreadingTCPServer((PUBLIC_HTTPS, 443), Echo)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((GATEWAY, 53))
        print("echo-ready", flush=True)
        while True:
            packet, remote = sock.recvfrom(4096)
            if packet != b"no-reply":
                sock.sendto(packet, remote)


def check(private, ip, nft):
    run(ip, "link", "set", "lo", "up")
    for interface, address in (
        ("vpn-fixture", "10.64.0.2/24"),
        ("wan-fixture", "192.0.2.2/24"),
    ):
        run(ip, "link", "add", interface, "type", "dummy")
        run(ip, "addr", "add", address, "dev", interface)
        run(ip, "link", "set", interface, "up")
    run(ip, "link", "add", "mesh-fixture", "type", "veth", "peer", "name", "mesh-peer")
    run(ip, "addr", "add", "100.64.0.1/16", "dev", "mesh-fixture")
    run(ip, "link", "set", "mesh-fixture", "up")
    run(ip, "route", "add", GATEWAY, "via", "100.64.0.2", "dev", "mesh-fixture", "table", "7120")
    run(
        ip,
        "route",
        "add",
        PUBLIC_HTTPS,
        "via",
        "100.64.0.2",
        "dev",
        "mesh-fixture",
        "table",
        "7120",
    )
    run(ip, "route", "add", "default", "dev", "vpn-fixture", "table", "1836018789")
    run(ip, "route", "add", "default", "dev", "wan-fixture")
    run(ip, "rule", "add", "pref", "110", "lookup", "7120")

    def connect_vpn():
        # Mullvad leaves priorities unspecified: Linux inserts these before
        # the first non-local rule, including any fixed-priority exception.
        run(ip, "rule", "add", "not", "fwmark", FW_MARK, "lookup", "1836018789")
        run(ip, "rule", "add", "lookup", "main", "suppress_prefixlength", "0")

    connect_vpn()
    # Model Mullvad's ct-mark allow, route-aware source NAT, reply mark, and
    # DNS rejection. A real echo peer checks the entire UDP reply path too.
    # NetBird overwrites the connection mark after output, before source NAT.
    # Omitting this real rule gives a false-positive routing-only regression.
    run(nft, "add", "table", "ip", "netbird_fixture")
    run(
        nft,
        "add",
        "chain",
        "ip",
        "netbird_fixture",
        "postrouting",
        "{ type filter hook postrouting priority -150; policy accept; }",
    )
    run(
        nft,
        "add",
        "rule",
        "ip",
        "netbird_fixture",
        "postrouting",
        "oifname",
        "mesh-fixture",
        "ct",
        "state",
        "new",
        "ct",
        "mark",
        "set",
        "0x0001bd11",
    )
    run(nft, "add", "table", "inet", "mullvad_fixture")
    for name, declaration in (
        ("output", "{ type filter hook output priority 0; policy accept; }"),
        ("nat", "{ type nat hook postrouting priority 100; policy accept; }"),
        ("prerouting", "{ type filter hook prerouting priority -199; policy accept; }"),
    ):
        run(nft, "add", "chain", "inet", "mullvad_fixture", name, declaration)
    run(
        nft,
        "add",
        "rule",
        "inet",
        "mullvad_fixture",
        "output",
        "ct",
        "mark",
        private.MARK,
        "accept",
    )
    run(nft, "add", "rule", "inet", "mullvad_fixture", "output", "udp", "dport", "53", "reject")
    run(nft, "add", "rule", "inet", "mullvad_fixture", "output", "oifname", "vpn-fixture", "accept")
    run(nft, "add", "rule", "inet", "mullvad_fixture", "output", "oifname", "lo", "accept")
    run(nft, "add", "rule", "inet", "mullvad_fixture", "output", "reject")
    run(
        nft,
        "add",
        "rule",
        "inet",
        "mullvad_fixture",
        "nat",
        "oifname",
        "vpn-fixture",
        "ct",
        "mark",
        private.MARK,
        "drop",
    )
    run(
        nft,
        "add",
        "rule",
        "inet",
        "mullvad_fixture",
        "nat",
        "ct",
        "mark",
        private.MARK,
        "masquerade",
    )
    run(
        nft,
        "add",
        "rule",
        "inet",
        "mullvad_fixture",
        "prerouting",
        "ct",
        "mark",
        private.MARK,
        "meta",
        "mark",
        "set",
        FW_MARK,
    )

    def route(address, protocol="udp", port=53, mark=None):
        return json.loads(
            run(
                ip,
                "-j",
                "route",
                "get",
                address,
                "ipproto",
                protocol,
                "dport",
                str(port),
                *(["mark", mark] if mark else []),
            )
        )[0]["dev"]

    def dns_roundtrip(allowed, sock=None):
        if sock is None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as fresh:
                return dns_roundtrip(allowed, fresh)
        sock.settimeout(2)
        try:
            sock.sendto(b"fixture", (GATEWAY, 53))
            if allowed:
                assert sock.recvfrom(4096)[0] == b"fixture"
                return
        except OSError as error:
            if allowed or error.errno != errno.EPERM:
                raise
        else:
            raise AssertionError("DNS escaped the fail-closed guard")

    def https_roundtrip(allowed, sock=None):
        if sock is None:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as fresh:
                return https_roundtrip(allowed, fresh)
        sock.settimeout(1)
        try:
            try:
                sock.getpeername()
            except OSError:
                sock.connect((PUBLIC_HTTPS, 443))
            sock.sendall(b"fixture")
            assert sock.recv(4096) == b"fixture"
        except (TimeoutError, PermissionError, ConnectionRefusedError):
            if allowed:
                raise
        else:
            assert allowed, "Revoked/public HTTPS escaped the fail-closed guard"

    peer = subprocess.Popen(
        ["unshare", "--net", "python3", "-B", __file__, "--echo-peer"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    retained = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unreplied = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    retained_https = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        assert peer.stdout.readline().strip() == "namespace-ready"
        run(ip, "link", "set", "mesh-peer", "netns", str(peer.pid))
        peer.stdin.write("configure\n")
        peer.stdin.flush()
        assert peer.stdout.readline().strip() == "echo-ready"
        assert route(GATEWAY) == "vpn-fixture", "fixture must reproduce conflicting routing"
        dns_roundtrip(False)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret, https_secret, routed_secret = root / "gateway", root / "https", root / "routed"
            secret.write_text(GATEWAY)
            https_secret.write_text("100.64.0.10")
            routed_secret.write_text(PUBLIC_HTTPS)

            def manage(action, include_routed=True):
                private.manage(
                    action,
                    "mesh-fixture",
                    secret,
                    root / "state",
                    nft,
                    https_secret,
                    routed_secret if include_routed else None,
                )

            manage("apply")
            dns_roundtrip(True, retained)
            https_roundtrip(True, retained_https)
            unreplied.sendto(b"no-reply", (GATEWAY, 53))
            # Recreate Mullvad's rules as if it reconnected after the service
            # applied its exceptions. A fixed priority 100 fails at this seam.
            run(ip, "rule", "del", "not", "fwmark", FW_MARK, "lookup", "1836018789")
            run(ip, "rule", "del", "lookup", "main", "suppress_prefixlength", "0")
            connect_vpn()
            dns_roundtrip(True)
            https_roundtrip(True)
            run(ip, "route", "del", PUBLIC_HTTPS, "dev", "mesh-fixture", "table", "7120")
            assert route(PUBLIC_HTTPS, "tcp", 443, FW_MARK) == "wan-fixture"
            https_roundtrip(False)
            run(
                ip,
                "route",
                "add",
                PUBLIC_HTTPS,
                "via",
                "100.64.0.2",
                "dev",
                "mesh-fixture",
                "table",
                "7120",
            )
            https_roundtrip(True)
            assert route(PUBLIC_HTTPS, "tcp", 80) == "vpn-fixture"
            assert route(PUBLIC_HTTPS, "udp", 443) == "vpn-fixture"
            assert route(PUBLIC_HTTPS, "udp", 53) == "vpn-fixture"
            for protocol, port in (("udp", 53), ("tcp", 53), ("tcp", 443)):
                assert route(GATEWAY, protocol, port, FW_MARK) == "mesh-fixture"
            assert route(GATEWAY, "udp", 443) == "vpn-fixture"
            assert route(GATEWAY, "tcp", 80) == "vpn-fixture"
            assert route("203.0.113.10", "tcp", 443) == "vpn-fixture"
            before = run(ip, "-j", "rule", "show")
            manage("apply")
            assert run(ip, "-j", "rule", "show") == before
            dns_roundtrip(True)
            # A marked scope with no overlay route MUST NOT exit via WAN.
            run(ip, "route", "del", GATEWAY, "dev", "mesh-fixture", "table", "7120")
            assert route(GATEWAY, mark=FW_MARK) == "wan-fixture"
            dns_roundtrip(False)
            run(
                ip,
                "route",
                "add",
                GATEWAY,
                "via",
                "100.64.0.2",
                "dev",
                "mesh-fixture",
                "table",
                "7120",
            )
            dns_roundtrip(True)
            # Model endpoints with an overlay route already in main (like
            # mesh peer addresses). Revocation must also stop unreplied NEW
            # flows before NetBird's postrouting overwrites their ct marks.
            run(ip, "route", "add", GATEWAY, "via", "100.64.0.2", "dev", "mesh-fixture")
            run(ip, "route", "add", PUBLIC_HTTPS, "via", "100.64.0.2", "dev", "mesh-fixture")
            manage("apply", include_routed=False)
            https_roundtrip(False, retained_https)
            https_roundtrip(False)
            dns_roundtrip(True)
            secret.write_text("198.51.100.11")
            manage("apply")
            dns_roundtrip(False)
            dns_roundtrip(False, retained)  # Previously marked conntrack flow.
            dns_roundtrip(False, unreplied)
            secret.unlink()
            https_secret.unlink()
            routed_secret.unlink()
            manage("revoke", include_routed=False)
            dns_roundtrip(False)
            dns_roundtrip(False, retained)
            dns_roundtrip(False, unreplied)
            assert route("203.0.113.10", "tcp", 443) == "vpn-fixture"
    finally:
        retained.close()
        unreplied.close()
        retained_https.close()
        peer.terminate()
        peer.communicate(timeout=5)
    print("UDP roundtrip, VPN reconnect, missing-route guard, rotation, and revocation passed")


def main():
    if len(sys.argv) != 2 or str(Path("/proc/self/ns/net").readlink()) == sys.argv[1]:
        raise RuntimeError("This helper requires an isolated network namespace")
    spec = importlib.util.spec_from_file_location(
        "private_access", ROOT / "modules/nixos/networking/netbird-mullvad-private.py"
    )
    private = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(private)
    check(private, shutil.which("ip"), shutil.which("nft"))


if __name__ == "__main__":
    if sys.argv[1:] == ["--echo-peer"]:
        echo_peer()
    else:
        main()
