#!/usr/bin/env python3
"""Evaluate selected laptop hardware, lab, voice, and VPNs without activation."""

import json
import re
import subprocess


def evaluate(group, name, expression):
    if not re.fullmatch(r"[a-zA-Z0-9_.@-]+", name):
        raise ValueError("Invalid output name")
    return json.loads(
        subprocess.check_output(
            [
                "nix",
                "eval",
                "--json",
                "--no-write-lock-file",
                f'.#{group}."{name}".config',
                "--apply",
                expression,
            ],
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

system = evaluate(
    "nixosConfigurations",
    system_name,
    """c: {
      inherit (c.networking) hostName;
      inherit (c.system) stateVersion;
      drivers = c.services.xserver.videoDrivers;
      root = c.fileSystems."/".device;
      boot = c.fileSystems."/boot".device;
      wifi = c.networking.networkmanager.enable;
      niri = c.programs.niri.enable;
      gnome = c.services.desktopManager.gnome.enable;
      fan = c.services.mbpfan.enable;
      power = c.services.power-profiles-daemon.enable;
      tlp = c.services.tlp.enable;
      ssh = { inherit (c.services.openssh) enable settings; };
      steam = c.programs.steam.enable;
      mullvad = c.services.mullvad-vpn.enable;
      netbird = c.services.netbird.clients.default.name;
      tailscale = c.services.tailscale.enable;
      tailscaleFlags = c.services.tailscale.extraSetFlags;
      camera = c.hardware.facetimehd.enable;
      trim = c.services.fstrim.enable;
      graphicsPackages = map (p: p.pname or p.name) c.hardware.graphics.extraPackages;
      kvm = builtins.elem "kvm" c.users.users.${builtins.head c.services.openssh.settings.AllowUsers}.extraGroups;
    }""",
)
assert system["drivers"] == ["modesetting"], system["drivers"]
assert system["stateVersion"] == "26.05"
assert all(system[key] for key in ["wifi", "niri", "gnome", "fan", "power"])
assert all(system[key].startswith("/dev/disk/by-uuid/") for key in ["root", "boot"])
assert not system["steam"] and not system["tlp"]
assert all(system[key] for key in ["mullvad", "tailscale", "camera", "trim", "kvm"])
assert system["netbird"]
assert "intel-vaapi-driver" in system["graphicsPackages"]
assert "--accept-dns=false" in system["tailscaleFlags"]
assert "--accept-routes=false" in system["tailscaleFlags"]
assert "--ssh=false" in system["tailscaleFlags"]
assert system["ssh"]["enable"]
assert not system["ssh"]["settings"]["PasswordAuthentication"]
assert not system["ssh"]["settings"]["KbdInteractiveAuthentication"]
assert system["ssh"]["settings"]["PermitRootLogin"] == "no"

home = evaluate(
    "homeConfigurations",
    home_name,
    """c: {
      packages = map (p: p.pname or p.name) c.home.packages;
      niri = c.xdg.configFile."niri/config.kdl".text;
      voice = c.systemd.user.services.voxtype.Service.ExecStart;
      reInitialized = builtins.hasAttr "initializePiRe" c.home.activation;
      vpnLauncher = builtins.hasAttr "netbird" c.xdg.desktopEntries;
      fontSizes = c.stylix.fonts.sizes;
    }""",
)
packages = home["packages"]
for prefix in ["open-design", "steam"]:
    assert not any(name.startswith(prefix) for name in packages), prefix
for required in ["codex-no-auto-daemon", "opencode-cli", "pi-re", "voxtype", "whisper"]:
    assert any(name.startswith(required) for name in packages), required
assert "scale 2" in home["niri"]
assert "touchpad {" in home["niri"]
assert "spawn-at-startup" in home["niri"]
assert "voxtype-pi-action" in home["niri"]
assert home["voice"] and home["reInitialized"] and home["vpnLauncher"]
assert "mullvad-vpn.desktop" in home["niri"]
assert "netbird.desktop" in home["niri"]
assert home["niri"].count("spawn-at-startup") == 8
assert "XF86KbdBrightnessUp" in home["niri"]
assert "XF86KbdBrightnessDown" in home["niri"]
assert "Mod+Shift+S" in home["niri"]
assert "Mod+Shift+BackSpace" in home["niri"]
assert home["fontSizes"] == {"desktop": 11, "applications": 12, "terminal": 13, "popups": 11}
print("Laptop hardware, lab, voice, and VPN profile checks passed.")
