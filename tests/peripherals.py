#!/usr/bin/env python3
"""Verify scoped USB controls without probing hardware; run after previews."""

import json
import re
import subprocess
from pathlib import Path


def evaluate(output, expression):
    return json.loads(
        subprocess.check_output(
            ["nix", "eval", "--json", "--no-write-lock-file", output, "--apply", expression],
            text=True,
        )
    )


systems = evaluate(
    ".#nixosConfigurations",
    """hosts: builtins.mapAttrs (_: h: let c = h.config; in {
      enabled = c.services.ratbagd.enable;
      openrgbServer = c.services.hardware.openrgb.enable;
      kernelModules = c.boot.kernelModules;
      gpu = if c.systemd.services ? gpu-lighting then {
        inherit (c.systemd.services.gpu-lighting) wantedBy wants after;
        inherit (c.systemd.services.gpu-lighting.serviceConfig) Type ExecStart ExecStopPost;
      } else null;
      ram = if c.systemd.services ? ram-lighting then {
        inherit (c.systemd.services.ram-lighting) wantedBy;
        inherit (c.systemd.services.ram-lighting.serviceConfig)
          Type RemainAfterExit ExecStart ExecStopPost NoNewPrivileges ProtectSystem;
      } else null;
      permissions = map toString (builtins.filter
        (p: p.name == "desktop-peripheral-permissions") c.services.udev.packages);
    }) hosts""",
)
for name, config in systems.items():
    if not config["enabled"]:
        assert not config["permissions"]
        assert config["ram"] is None and config["gpu"] is None
        print(f"{name}: no desktop peripheral permissions")
        continue
    assert not config["openrgbServer"]
    assert "i2c-dev" not in config["kernelModules"]
    assert len(config["permissions"]) == 1
    assert config["ram"]["wantedBy"] == ["multi-user.target"]
    assert config["gpu"]["wantedBy"] == ["multi-user.target"]
    assert config["gpu"]["wants"] == ["ram-lighting.service"]
    assert "ram-lighting.service" in config["gpu"]["after"]
    assert "gpu-lighting.py" in config["gpu"]["ExecStart"]
    assert "openrgb-exact-gpu-validation" in config["gpu"]["ExecStart"]
    assert "--cleanup" in config["gpu"]["ExecStopPost"]
    assert config["ram"]["Type"] == "oneshot" and config["ram"]["RemainAfterExit"]
    assert config["ram"]["NoNewPrivileges"] and config["ram"]["ProtectSystem"] == "strict"
    assert "ram-lighting.py" in config["ram"]["ExecStart"]
    assert "--cleanup" in config["ram"]["ExecStopPost"]
    path = Path(config["permissions"][0]) / "lib/udev/rules.d/70-desktop-peripherals.rules"
    assert path.exists(), "Build just preview before running this test"
    rules = [
        line
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    usb_rules = [rule for rule in rules if "ATTRS{" in rule]
    keyboard_rules = [rule for rule in rules if "ENV{" in rule]
    assert len(rules) == 3 and len(usb_rules) == 2 and len(keyboard_rules) == 1
    assert re.fullmatch(
        r'SUBSYSTEM=="hidraw", KERNEL=="hidraw\*", '
        r'ENV\{ID_VENDOR_ID\}=="[0-9a-f]{4}", '
        r'ENV\{ID_MODEL_ID\}=="[0-9a-f]{4}", '
        r'ENV\{ID_USB_INTERFACE_NUM\}=="[0-9a-f]{2}", TAG\+="uaccess"',
        keyboard_rules[0],
    )
    for rule in usb_rules:
        assert re.fullmatch(
            r'SUBSYSTEM=="hidraw", KERNEL=="hidraw\*", '
            r'ATTRS\{idVendor\}=="[0-9a-f]{4}", '
            r'ATTRS\{idProduct\}=="[0-9a-f]{4}", TAG\+="uaccess"',
            rule,
        )
    print(f"{name}: mouse service, device-scoped seat ACLs, no RGB server or I2C access")

homes = evaluate(
    ".#homeConfigurations",
    """homes: builtins.mapAttrs (_: h: let
      c = h.config;
      tools = builtins.filter (p: (p.pname or p.name) == "cooler-status") c.home.packages;
      rgb = builtins.filter (p: (p.pname or p.name) == "openrgb-usb") c.home.packages;
      restore = builtins.filter (p: (p.pname or p.name) == "restore-usb-lighting") c.home.packages;
    in {
      packages = map (p: p.pname or p.name) c.home.packages;
      statusScript = if tools == [] then null else "${builtins.head tools}/bin/cooler-status";
      rgbScript = if rgb == [] then null else "${builtins.head rgb}/bin/openrgb-usb";
      launcher = if builtins.hasAttr "org.openrgb.OpenRGB" c.xdg.desktopEntries
        then c.xdg.desktopEntries."org.openrgb.OpenRGB".exec else null;
      coolerLauncher = if builtins.hasAttr "cooler-status" c.xdg.desktopEntries
        then c.xdg.desktopEntries.cooler-status.exec else null;
      keyboardLauncher = builtins.hasAttr "keyboard-config" c.xdg.desktopEntries;
      restoration = if c.systemd.user.services ? usb-lighting then {
        inherit (c.systemd.user.services.usb-lighting) Unit Service Install;
        script = "${builtins.head restore}/bin/restore-usb-lighting";
      } else null;
    }) homes""",
)
for name, config in homes.items():
    if config["statusScript"] is None:
        assert config["launcher"] is None and config["coolerLauncher"] is None
        assert config["rgbScript"] is None and config["restoration"] is None
        print(f"{name}: no desktop-only control apps")
        continue
    assert {"piper", "openrgb", "liquidctl"} <= set(config["packages"])
    restore = config["restoration"]
    assert restore["Install"]["WantedBy"] == ["graphical-session.target"]
    assert restore["Unit"]["PartOf"] == ["graphical-session.target"]
    assert restore["Service"]["Type"] == "oneshot" and restore["Service"]["RemainAfterExit"]
    assert restore["Service"]["ExecStart"] == [restore["script"]]
    assert "usb-lighting.py" in Path(restore["script"]).read_text()
    assert config["launcher"].startswith(config["rgbScript"] + " --gui --device ")
    assert re.search(r"--zone 1 --size [1-9][0-9]*$", config["launcher"])
    rgb = Path(config["rgbScript"]).read_text()
    assert "--nodetect" not in rgb
    assert "@allowedDevices@" not in rgb and "@openrgb@" not in rgb
    for boundary in ("--ro-bind / /", "--dev /dev", "--proc /proc", "--unshare-all"):
        assert boundary in rgb
    assert 'bindings+=(--dev-bind "$node" "$node")' in rgb
    assert '--bind "$config_dir" "$config_dir"' in rgb
    assert '--tmpfs "$rules_dir"' in rgb
    assert '--ro-bind "$scoped_rules" "$rules_dir/60-openrgb.rules"' in rgb
    assert "--setenv LIBGL_ALWAYS_SOFTWARE 1" in rgb
    assert '--config "$config_dir" --noautoconnect "$@"' in rgb
    assert 'flock --nonblock "$XDG_RUNTIME_DIR/usb-lighting.lock" bwrap' in rgb
    assert not config["keyboardLauncher"]
    assert "--gtk-single-instance=false --wait-after-command=true -e " in config["coolerLauncher"]
    assert config["coolerLauncher"].endswith(config["statusScript"])
    script = Path(config["statusScript"])
    assert script.exists(), "Build just home-preview before running this test"
    assert re.search(
        r"^exec liquidctl --vendor 0x[0-9a-f]{4} --product 0x[0-9a-f]{4} status$",
        script.read_text(),
        re.MULTILINE,
    )
    print(f"{name}: device-isolated USB lighting and selected-device telemetry only")
