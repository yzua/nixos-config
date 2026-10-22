#!/usr/bin/env python3
"""Check detected local streaming roles; optional selectors also allow cross-host checks."""

import json
import os
import re
import shlex
import subprocess


def evaluate(reference, expression):
    return json.loads(
        subprocess.check_output(
            ["nix", "eval", "--json", "--no-write-lock-file", reference, "--apply", expression],
            text=True,
        )
    )


system_name, home_name = subprocess.check_output(
    [
        "bash",
        "-eu",
        "-c",
        'source scripts/config.sh; select_system; select_home; printf "%s\\n%s\\n" "$NIXOS_CONFIG" "$HOME_CONFIG"',
    ],
    text=True,
).splitlines()
assert all(re.fullmatch(r"[a-zA-Z0-9_.@-]+", name) for name in [system_name, home_name])
system_ref = f'.#nixosConfigurations."{system_name}"'
host = evaluate(
    system_ref + ".config",
    """c: if !c.services.sunshine.enable then null else {
      sunshine = {
        inherit (c.services.sunshine) enable autoStart openFirewall capSysAdmin settings applications;
        cudaDisabled = builtins.elem "-DSUNSHINE_ENABLE_CUDA=OFF" c.services.sunshine.package.cmakeFlags;
      };
      firewall = {
        inherit (c.networking.firewall) enable allInterfaces extraCommands extraInputRules trustedInterfaces;
        nftables = c.networking.nftables.enable;
      };
      wrapper = builtins.hasAttr "sunshine" c.security.wrappers;
      uinput = c.hardware.uinput.enable;
      publishing = c.services.avahi.publish.enable;
      service = c.systemd.user.services.sunshine;
    }""",
)
if os.environ.get("NIXOS_CONFIG") and host is None:
    raise SystemExit("Explicitly selected system is not a Sunshine host.")
if host is not None:
    sunshine = host["sunshine"]
    assert sunshine["enable"] and sunshine["autoStart"]
    assert not sunshine["openFirewall"] and not sunshine["capSysAdmin"]
    assert not host["wrapper"] and host["uinput"]
    assert not host["publishing"] and not sunshine["cudaDisabled"]
    settings = sunshine["settings"]
    assert settings["capture"] == "wlr"
    assert settings["encoder"] == "nvenc"
    assert settings["origin_web_ui_allowed"] == "pc"
    assert settings["upnp"] == "disabled"
    assert settings["address_family"] == "ipv4"
    assert settings["lan_encryption_mode"] == settings["wan_encryption_mode"] == 2
    assert settings["controller"] == "enabled"
    assert settings["gamepad"] == "x360"
    apps = sunshine["applications"]["apps"]
    assert len(apps) == 2
    assert set(apps[0]) == {"name"}
    assert set(apps[1]) == {"name", "prep-cmd", "detached"}
    assert len(apps[1]["prep-cmd"]) == 1
    assert set(apps[1]["prep-cmd"][0]) == {"do", "undo"}
    assert len(apps[1]["detached"]) == 1
    assert apps[1]["detached"][0].endswith("/bin/steam -bigpicture")
    assert host["service"]["serviceConfig"]["UMask"] == "0077"
    assert host["service"]["unitConfig"]["ConditionUser"]
    firewall = host["firewall"]
    assert firewall["enable"] and firewall["trustedInterfaces"] == ["lo"]
    assert not firewall["nftables"] and not firewall["extraInputRules"]
    for interface in firewall["allInterfaces"].values():
        for protocol, protected in [
            ("TCP", {47984, 47989, 47990, 48010}),
            ("UDP", {47998, 47999, 48000}),
        ]:
            assert not protected & set(interface[f"allowed{protocol}Ports"])
            for port_range in interface[f"allowed{protocol}PortRanges"]:
                assert not any(port_range["from"] <= p <= port_range["to"] for p in protected)
    remote = evaluate(system_ref + "._module.specialArgs.setup.remoteDesktop", "x: x")
    streaming_rules = [
        shlex.split(line)
        for line in firewall["extraCommands"].splitlines()
        if "-j nixos-fw-accept" in line or "-j ACCEPT" in line
    ]
    clients = {remote["clientAddress"], remote["tv"]["clientAddress"]}
    assert len(clients) == 2
    assert apps[0]["name"] == remote["appName"]
    assert apps[1]["name"] == remote["tv"]["appName"]
    monitors = evaluate(system_ref + "._module.specialArgs.setup.monitors", "x: x")
    primary = next(monitor for monitor in monitors if monitor["primary"])
    for action, mode in [("do", remote["tv"]["mode"]), ("undo", primary["mode"])]:
        # Sunshine uses Boost.Process, not a shell: POSIX single quotes are not
        # understood. Only pass a bare script path; shell quoting belongs inside.
        command = apps[1]["prep-cmd"][0][action]
        assert re.fullmatch(r"/nix/store/[a-z0-9]+-sunshine-tv-mode-[^\s/]+", command), (
            "Sunshine prep commands must be bare wrapper paths, not shell-quoted argv"
        )
        context = evaluate(
            system_ref + ".config.services.sunshine.applications.apps",
            f'apps: builtins.getContext ((builtins.head ((builtins.elemAt apps 1).prep-cmd))."{action}")',
        )
        derivations = json.loads(
            subprocess.check_output(["nix", "derivation", "show", *context], text=True)
        )
        # Nix 2.34+ wraps the derivation map in a versioned object.
        derivations = derivations.get("derivations", derivations)
        assert len(derivations) == 1
        script = next(iter(derivations.values()))["env"]["text"]
        lines = [line for line in script.splitlines() if line and not line.startswith("#!")]
        assert len(lines) == 1
        argv = shlex.split(lines[0])
        assert argv[0] == "exec" and argv[1].endswith("/bin/niri")
        assert argv[2:] == ["msg", "output", primary["match"], "mode", mode]
    assert len(streaming_rules) == 2 * len(clients)
    expected = {
        (client + "/32", protocol, ports)
        for client in clients
        for protocol, ports in [
            ("tcp", "47984,47989,48010"),
            ("udp", "47998:48000"),
        ]
    }
    actual = set()
    for rule in streaming_rules:
        assert rule[:3] == ["iptables", "-A", "nixos-fw"]
        assert rule[rule.index("-i") + 1] == remote["hostInterface"]
        actual.add(
            (
                rule[rule.index("-s") + 1],
                rule[rule.index("-p") + 1],
                rule[rule.index("--dports") + 1],
            )
        )
        assert rule[rule.index("-d") + 1] == remote["hostAddress"]
        assert rule[rule.index("--dports") + 1] in {"47984,47989,48010", "47998:48000"}
        assert rule[-2:] == ["-j", "nixos-fw-accept"]
    assert actual == expected
    print(f"{system_name}: restricted encrypted Sunshine LAN policy checks passed.")

client = evaluate(
    f'.#homeConfigurations."{home_name}".config',
    """c: if !(builtins.hasAttr "pc-desktop" c.xdg.desktopEntries) then null else {
      packages = map (p: p.pname or p.name) c.home.packages;
      launcher = { inherit (c.xdg.desktopEntries.pc-desktop) exec terminal; };
    }""",
)
if os.environ.get("HOME_CONFIG") and client is None:
    raise SystemExit("Explicitly selected home is not a Moonlight client.")
if client is not None:
    assert "moonlight-qt" in client["packages"]
    assert any(name.startswith("pc-desktop") for name in client["packages"])
    assert not client["launcher"]["terminal"]
    assert client["launcher"]["exec"].endswith("/bin/pc-desktop")
    print(f"{home_name}: Moonlight client launcher checks passed.")
if host is None and client is None:
    raise SystemExit("Selected local outputs have no configured streaming role.")
