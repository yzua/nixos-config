#!/usr/bin/env python3
"""Check declarative playback-only EQ; run after building a home preview."""

import configparser
import json
import os
import subprocess
import tempfile
from pathlib import Path

configs = json.loads(
    subprocess.check_output(
        [
            "nix",
            "eval",
            "--json",
            "--no-write-lock-file",
            ".#homeConfigurations",
            "--apply",
            """homes: builtins.mapAttrs (_: h: let c = h.config; in {
              niri = c.xdg.configFile."niri/config.kdl".text;
              enabled = c.services.easyeffects.enable;
              presets = c.services.easyeffects.extraPresets;
              service = if c.services.easyeffects.enable then
                c.systemd.user.services.easyeffects else null;
              files = builtins.listToAttrs (map (n: {
                name = n; value = toString c.xdg.dataFile.${n}.source;
              }) (builtins.filter (n: builtins.match "easyeffects/.*" n != null)
                (builtins.attrNames c.xdg.dataFile)));
            }) homes""",
        ],
        text=True,
    )
)
for name, config in configs.items():
    assert "noctalia-audio-startup/bin/noctalia-audio-startup" in config["niri"]
    if not config["enabled"]:
        assert not config["files"]
        print(f"{name}: EasyEffects remains disabled")
        continue
    presets = config["presets"]
    eq = presets["headset-gentle"]["output"]["equalizer#0"]
    assert eq["input-gain"] <= -sum(max(0, b["gain"]) for b in eq["left"].values())
    assert eq["left"] == eq["right"] and not eq["split-channels"]
    assert len(eq["left"]) == eq["num-bands"] == 3
    assert not eq["bypass"] and eq["output-gain"] == 0
    assert presets["headset-gentle"]["output"]["plugins_order"] == ["equalizer#0"]
    assert presets["unprocessed"] == {"output": {"blocklist": [], "plugins_order": []}}
    assert all(set(p) == {"output"} for p in presets.values())
    mappings = [p for p in config["files"] if "/autoload/output/" in p]
    assert len(mappings) == 1
    for path, source in config["files"].items():
        assert Path(source).exists(), "Build just home-preview before running this test"
        data = json.loads(Path(source).read_text())
        if path in mappings:
            expected = (data["device"] + ":" + data["device-profile"]).replace("/", "_")
            assert path.endswith(f"/{expected}.json")
            assert data["preset-name"] == "headset-gentle"
        else:
            assert data == presets[Path(path).stem]
    service = config["service"]
    assert service["Install"]["WantedBy"] == ["graphical-session.target"]
    assert any("--service-mode" in command for command in service["Service"]["ExecStart"])
    for dependency in ("pipewire.service", "pipewire-pulse.service", "wireplumber.service"):
        assert dependency in service["Unit"]["After"], f"Missing ordering: {dependency}"
        assert dependency in service["Unit"]["Wants"], f"Missing dependency: {dependency}"
    startup = service["Service"]["ExecStartPre"]
    assert isinstance(startup, list) and len(startup) == 2
    assert startup[0].endswith("/bin/wait-for-audio-output")
    # Exercise only the settings writer; readiness has separate offline graph tests.
    # Never wait for or change the caller's live audio in this test.
    with tempfile.TemporaryDirectory(prefix="easyeffects-test-") as tmp:
        env = os.environ | {"XDG_CONFIG_HOME": tmp}
        subprocess.run([startup[1]], env=env, check=True)
        path = Path(tmp) / "easyeffects/db/easyeffectsrc"
        settings = configparser.ConfigParser()
        settings.read(path)
        assert not settings.getboolean("EffectsPipelines", "processAllInputs")
        assert settings.getboolean("EffectsPipelines", "processAllOutputs")
        assert settings["StreamOutputs"]["plugins"] == ""
        assert not settings.getboolean("StreamInputs", "listenToMic")
        assert not settings.getboolean("StreamInputs", "listenToMicIncludesOutputEffects")
        assert not settings.getboolean("Window", "autostartOnLogin")
        assert settings.getboolean("Window", "outputAutoloadingUsesFallback")
        assert settings["Window"]["outputAutoloadingFallbackPreset"] == "unprocessed"
        path.write_text(path.read_text() + "\n[UserPreference]\nkeepMe=true\n")
        subprocess.run([startup[1]], env=env, check=True)
        settings.read(path)
        assert settings.getboolean("UserPreference", "keepMe")
    print(f"{name}: EQ, route mapping, flat fallback, startup and mic safety passed")
