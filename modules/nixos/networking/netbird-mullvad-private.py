#!/usr/bin/env python3
"""Manage a narrow Mullvad exception using a root-only runtime endpoint secret."""

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


def rules(addresses, https_addresses, interface, active, active_https):
    lines = [
        f"table inet {TABLE}",
        f"delete table inet {TABLE}",
        f"table inet {TABLE} {{",
        "  chain marking {",
        "    type filter hook output priority -110; policy accept;",
    ]
    if active is not None:
        for protocol, ports in (("udp", "53"), ("tcp", "{ 53, 443 }")):
            lines.append(
                f'    oifname "{interface}" ip daddr {active} {protocol} dport {ports}'
                f" counter ct mark set {MARK}"
            )
    if active_https is not None:
        lines.append(
            f'    oifname "{interface}" ip daddr {active_https} tcp dport 443'
            f" counter ct mark set {MARK}"
        )
    lines.extend(
        ["  }", "  chain guard {", "    type filter hook output priority -100; policy accept;"]
    )
    for address in sorted(addresses | https_addresses):
        # Port-specific guards retain old scopes while allowing a selected
        # HTTPS endpoint to have been a gateway in a previous generation.
        scopes = [("tcp", "443", address in {active, active_https})]
        if address in addresses:
            scopes.extend([("udp", "53", address == active), ("tcp", "53", address == active)])
        for protocol, port, allowed in scopes:
            condition = f'oifname != "{interface}" ' if allowed else ""
            lines.append(
                f"    {condition}ip daddr {address} {protocol} dport {port} ct mark {MARK} reject"
            )
    return "\n".join([*lines, "  }", "}", ""])


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


def manage(action, interface, secret, state_directory, nft, https_secret=None):
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
    active = endpoint(secret.read_text()) if action == "apply" else None
    active_https = (
        endpoint(https_secret.read_text())
        if action == "apply" and https_secret is not None
        else None
    )
    if active is not None:
        addresses.add(active)
    if active_https is not None:
        https_addresses.add(active_https)
    if not addresses and not https_addresses:
        return
    # Preserve the union BEFORE changing the firewall, so interrupted activation
    # or secret rotation cannot forget old connection marks. Runtime only.
    staging = state_directory / "endpoints.pending"
    with open(staging, "w", opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
        json.dump({"gateways": sorted(addresses), "https": sorted(https_addresses)}, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staging, state_path)
    run_nft(nft, rules(addresses, https_addresses, interface, active, active_https))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("apply", "revoke"))
    parser.add_argument("interface")
    parser.add_argument("secret", type=Path)
    parser.add_argument("state_directory", type=Path)
    parser.add_argument("nft")
    parser.add_argument("https_secret", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        manage(
            args.action,
            args.interface,
            args.secret,
            args.state_directory,
            args.nft,
            args.https_secret,
        )
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError):
        # No tracebacks or exception text: both may contain private file content.
        print(
            "NetBird/Mullvad private firewall operation failed; no endpoint details logged",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
