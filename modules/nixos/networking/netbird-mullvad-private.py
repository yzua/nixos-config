#!/usr/bin/env python3
"""Manage scoped private NetBird routing/firewall exceptions from runtime secrets."""

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TABLE = "netbird_mullvad_private"
MARK = "0x00000f41"
# Mullvad's packet-routing exclusion mark. Its connection mark above grants
# the firewall exception and source NAT; both are confined below to exact
# endpoints/ports, with a post-routing overlay guard before source NAT.
ROUTE_MARK = "0x6d6f6c65"


def endpoint(value):
    """Validate without including the secret value in any error message."""
    try:
        address = ipaddress.IPv4Address(value.strip())
    except (ValueError, AttributeError):
        raise ValueError("Invalid private endpoint secret") from None
    if (
        not (address.is_private or address in ipaddress.IPv4Network("100.64.0.0/10"))
        or address.is_loopback
        or address.is_link_local
        or address.is_unspecified
        or address.is_multicast
        or address.is_reserved
    ):
        raise ValueError("Endpoint must be a private unicast IPv4 address")
    return str(address)


def routed_endpoint(value):
    """Only explicitly selected public unicast hosts may gain HTTPS routing."""
    try:
        address = ipaddress.IPv4Address(value.strip())
    except (ValueError, AttributeError):
        raise ValueError("Invalid routed HTTPS endpoint secret") from None
    if not address.is_global or address.is_multicast or address.is_reserved:
        raise ValueError("Routed HTTPS endpoint must be a global unicast IPv4 address")
    return str(address)


def rules(addresses, https_addresses, interface, active, active_https, active_routed=None):
    flows = []
    if active is not None:
        flows.extend(((active, "udp", "53"), (active, "tcp", "{ 53, 443 }")))
    for address in sorted({active_https, active_routed} - {None}):
        flows.append((address, "tcp", "443"))
    lines = [
        f"table inet {TABLE}",
        f"delete table inet {TABLE}",
        f"table inet {TABLE} {{",
        "  chain marking {",
        "    type route hook output priority -110; policy accept;",
    ]
    for address, protocol, ports in flows:
        lines.append(
            f"    ip daddr {address} {protocol} dport {ports}"
            f" counter ct mark set {MARK} meta mark set {ROUTE_MARK}"
        )
    lines.extend(
        [
            "  }",
            "  chain restore {",
            "    type filter hook postrouting priority -125; policy accept;",
        ]
    )
    for address, protocol, ports in flows:
        # NetBird overwrites NEW connection marks in postrouting at -150.
        # Restore only our selected, routed flows before the guard and before
        # Mullvad's source NAT (+100), or they retain the VPN's source address.
        lines.append(
            f'    oifname "{interface}" ip daddr {address} {protocol} dport {ports}'
            f" meta mark {ROUTE_MARK} counter ct mark set {MARK}"
        )
    lines.extend(
        # Route chains reroute only after the complete output hook. Check the
        # FINAL interface here, not the stale interface seen in output.
        ["  }", "  chain guard {", "    type filter hook postrouting priority -100; policy accept;"]
    )
    revoked = []
    for address in sorted(addresses | https_addresses):
        # Port-specific guards retain old scopes while allowing a selected
        # HTTPS endpoint to have been a gateway in a previous generation.
        scopes = [("tcp", "443", address in {active, active_https, active_routed})]
        if address in addresses:
            scopes.extend([("udp", "53", address == active), ("tcp", "53", address == active)])
        for protocol, port, allowed in scopes:
            condition = f'oifname != "{interface}" ' if allowed else ""
            match = f"ip daddr {address} {protocol} dport {port} ct mark {MARK} drop"
            lines.append(f"    {condition}{match}")
            if not allowed:
                revoked.append(f"    {match}")
    # Reject revoked marked flows before NetBird can overwrite their marks,
    # including UDP flows that have not received a reply (ct state NEW).
    return "\n".join(
        [
            *lines,
            "  }",
            "  chain revoked {",
            "    type filter hook output priority -100; policy accept;",
            *revoked,
            "  }",
            "}",
            "",
        ]
    )


def run_nft(binary, text):
    # nft parser errors can quote the private address: never relay its output.
    for flags in (("--check",), ()):
        result = subprocess.run(
            [binary, *flags, "--file", "-"],
            input=text,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                "Private firewall transaction failed; sensitive diagnostics suppressed"
            )


def manage(action, interface, secret, state_directory, nft, https_secret=None, routed_secret=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", interface):
        raise ValueError("Invalid NetBird interface name")
    state_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_path = state_directory / "endpoints.json"
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    # Upgrade the earlier gateway-only runtime state without forgetting marks.
    if isinstance(previous, list):
        previous = {"gateways": previous, "https": []}
    addresses = {endpoint(value) for value in previous.get("gateways", [])}
    https_addresses = {endpoint(value) for value in previous.get("https", [])}
    routed_addresses = {routed_endpoint(value) for value in previous.get("routed_https", [])}
    active = endpoint(secret.read_text()) if action == "apply" else None
    active_https = (
        endpoint(https_secret.read_text())
        if action == "apply" and https_secret is not None
        else None
    )
    active_routed = (
        routed_endpoint(routed_secret.read_text())
        if action == "apply" and routed_secret is not None
        else None
    )
    if active is not None:
        addresses.add(active)
    if active_https is not None:
        https_addresses.add(active_https)
    if active_routed is not None:
        routed_addresses.add(active_routed)
    if not addresses and not https_addresses and not routed_addresses:
        return
    # Preserve the union BEFORE changing the firewall, so interrupted activation
    # or secret rotation cannot forget old connection marks. Runtime only.
    staging = state_directory / "endpoints.pending"
    with open(staging, "w", opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
        json.dump(
            {
                "gateways": sorted(addresses),
                "https": sorted(https_addresses),
                "routed_https": sorted(routed_addresses),
            },
            handle,
        )
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staging, state_path)
    run_nft(
        nft,
        rules(
            addresses,
            https_addresses | routed_addresses,
            interface,
            active,
            active_https,
            active_routed,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("apply", "revoke"))
    parser.add_argument("interface")
    parser.add_argument("secret", type=Path)
    parser.add_argument("state_directory", type=Path)
    parser.add_argument("nft")
    parser.add_argument("https_secret", type=Path, nargs="?")
    parser.add_argument("--routed-https-secret", type=Path)
    args = parser.parse_args()
    try:
        manage(
            args.action,
            args.interface,
            args.secret,
            args.state_directory,
            args.nft,
            args.https_secret,
            args.routed_https_secret,
        )
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError):
        # No tracebacks or exception text: both may contain private file content.
        print(
            "NetBird/Mullvad private access operation failed; no endpoint details logged",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
