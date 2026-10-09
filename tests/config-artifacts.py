#!/usr/bin/env python3
"""Validate generated configs and activation/hooks using only isolated fixtures."""

import ast
import fcntl
import json
import os
import pty
import select
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREAMBLE = """
let
  root = builtins.toPath (builtins.getEnv "CONFIG_TEST_REPO");
  flake = builtins.getFlake (toString root);
"""


def evaluate(expression, environment):
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--impure",
            "--offline",
            "--no-write-lock-file",
            "--json",
            "--expr",
            PREAMBLE + expression,
        ],
        cwd=ROOT,
        env=dict(os.environ, CONFIG_TEST_REPO=str(ROOT), **environment),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


class WritableSettings(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vscode-settings-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "config/Code/User/settings.json"
        self.backups = self.root / "state/nixos"
        self.baseline = self.root / "baseline.json"
        self.baseline.write_text('{"fixture": true}\n')
        self.script = evaluate(
            """
  lib = flake.inputs.nixpkgs.lib;
  settings = import (root + "/home-manager/modules/vscode") {
    config.xdg = {
      configHome = builtins.getEnv "CONFIG_TEST_HOME";
      stateHome = builtins.getEnv "CONFIG_TEST_STATE";
    };
    lib = lib // { hm.dag.entryAfter = _: data: { inherit data; }; };
    pkgs.formats.json = _: { generate = _: _: builtins.getEnv "CONFIG_TEST_BASELINE"; };
  };
in settings.home.activation.vscodeWritableSettings.data
""",
            {
                "CONFIG_TEST_HOME": str(self.root / "config"),
                "CONFIG_TEST_STATE": str(self.root / "state"),
                "CONFIG_TEST_BASELINE": str(self.baseline),
            },
        )

    def run_activation(self, **environment):
        env = {key: value for key, value in os.environ.items() if key != "DRY_RUN"}
        env.update(environment)
        return subprocess.run(
            ["bash", "-e", "-c", self.script], env=env, capture_output=True, text=True, timeout=10
        )

    def existing(self, content="user-edited\n"):
        self.target.parent.mkdir(parents=True)
        self.target.write_text(content)

    def test_first_install_is_regular_private_file(self):
        result = self.run_activation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.target.is_symlink())
        self.assertEqual(self.target.read_bytes(), self.baseline.read_bytes())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.backups.exists())

    def test_identical_baseline_does_not_replace_or_back_up(self):
        self.existing(self.baseline.read_text())
        before = self.target.stat()
        result = self.run_activation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.stat().st_ino, before.st_ino)
        self.assertEqual(self.target.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertFalse(self.backups.exists())

    def test_modified_settings_are_backed_up_and_reset(self):
        self.existing()
        result = self.run_activation()
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list(self.backups.glob("vscode-settings.*/settings.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "user-edited\n")
        self.assertEqual(self.target.read_bytes(), self.baseline.read_bytes())

    def test_unsafe_targets_are_refused_without_mutation(self):
        self.target.parent.mkdir(parents=True)
        for kind in ("symlink", "directory"):
            with self.subTest(kind=kind):
                if kind == "symlink":
                    self.target.symlink_to(self.baseline)
                else:
                    self.target.mkdir()
                before = self.baseline.read_bytes()
                result = self.run_activation()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not a regular file", result.stderr)
                self.assertEqual(self.baseline.read_bytes(), before)
                self.assertFalse(self.backups.exists())
                if kind == "symlink":
                    self.target.unlink()
                else:
                    self.target.rmdir()

    def test_dry_run_never_writes_or_creates_directories(self):
        result = self.run_activation(DRY_RUN="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Would install writable", result.stdout)
        self.assertFalse(self.target.parent.exists())
        self.assertFalse(self.backups.exists())

    def test_replacement_failure_keeps_existing_settings(self):
        self.existing()
        bindir = self.root / "bin"
        bindir.mkdir()
        failure = bindir / "mv"
        failure.write_text("#!/usr/bin/env bash\nexit 1\n")
        failure.chmod(0o755)
        result = self.run_activation(PATH=f"{bindir}:{os.environ['PATH']}")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(), "user-edited\n")


class GitHooks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="git-hooks-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.bin = self.root / "tools/bin"
        self.bin.mkdir(parents=True)
        self.log = self.root / "calls"
        self.env = dict(
            os.environ,
            GIT_CONFIG_GLOBAL="/dev/null",
            GIT_CONFIG_SYSTEM="/dev/null",
            GIT_CONFIG_NOSYSTEM="1",
            CONFIG_TEST_CALLS=str(self.log),
        )
        subprocess.run(["git", "init", "-q", str(self.repo)], env=self.env, check=True)
        scanner = self.bin / "gitleaks"
        scanner.write_text("""#!/usr/bin/env bash
printf 'scan\\n' >> "$CONFIG_TEST_CALLS"
exit "${CONFIG_TEST_SCAN_EXIT:-0}"
""")
        scanner.chmod(0o755)
        self.hooks = evaluate(
            """
  git = import (root + "/home-manager/modules/terminal/git.nix") {
    config.xdg.configHome = "/fixture/config";
    setup.gitIdentity = { name = "fixture"; email = "fixture@example.invalid";
      githubEmail = "github@example.invalid"; signingKey = "/fixture/key.pub"; };
    pkgs = {
      writeShellScript = _: text: text;
      gitleaks = builtins.getEnv "CONFIG_TEST_TOOLS";
    };
  };
in git.programs.git.hooks
""",
            {"CONFIG_TEST_TOOLS": str(self.root / "tools")},
        )
        for name in self.hooks:
            local = self.repo / ".git/hooks" / name
            local.write_text('#!/usr/bin/env bash\nprintf "local\\n" >> "$CONFIG_TEST_CALLS"\n')
            local.chmod(0o755)

    def run_hook(self, name, *arguments, **environment):
        return subprocess.run(
            ["bash", "-c", self.hooks[name], "hook", *arguments],
            cwd=self.repo,
            env=dict(self.env, **environment),
            capture_output=True,
            text=True,
            timeout=10,
        )

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_precommit_scans_only_opted_in_repos_then_delegates(self):
        self.assertEqual(self.run_hook("pre-commit").returncode, 0)
        self.assertEqual(self.calls(), ["local"])
        self.log.unlink()
        (self.repo / ".gitleaks.toml").write_text("# fixture\n")
        self.assertEqual(self.run_hook("pre-commit").returncode, 0)
        self.assertEqual(self.calls(), ["scan", "local"])

    def test_scan_failure_blocks_repository_hook(self):
        (self.repo / ".gitleaks.toml").write_text("# fixture\n")
        self.assertNotEqual(self.run_hook("pre-commit", CONFIG_TEST_SCAN_EXIT="1").returncode, 0)
        self.assertEqual(self.calls(), ["scan"])

    def test_commit_subject_validation_and_repository_delegation(self):
        message = self.root / "message"
        for subject, accepted in [
            ("feat: fixture", True),
            ("fix(scope)!: fixture", True),
            ("Merge branch 'fixture'", True),
            ("Initial commit", True),
            ("unstructured subject", False),
            ("", False),
        ]:
            with self.subTest(subject=subject):
                self.log.unlink(missing_ok=True)
                message.write_text(subject + "\n")
                result = self.run_hook("commit-msg", str(message))
                self.assertEqual(result.returncode == 0, accepted, result.stderr)
                self.assertEqual(self.calls(), ["local"] if accepted else [])


class NetworkContracts(unittest.TestCase):
    def test_tor_mullvad_bypass_requires_both_services_before_creating_unit(self):
        results = evaluate(
            """
  lib = flake.inputs.nixpkgs.lib;
  modes = [ { tor = false; mullvad = false; }
    { tor = true; mullvad = false; } { tor = false; mullvad = true; }
    { tor = true; mullvad = true; } ];
  check = mode:
    let system = lib.nixosSystem {
      system = builtins.currentSystem;
      modules = [ (root + "/modules/nixos/networking/tor-mullvad-bypass.nix") {
        boot.isContainer = true;
        system.stateVersion = "26.05";
        services.tor.enable = mode.tor;
        services.mullvad-vpn.enable = mode.mullvad;
      } ];
    }; in {
      assertions = map (item: { inherit (item) assertion message; })
        (builtins.filter (item: !item.assertion && lib.hasPrefix "Tor/Mullvad bypass requires" item.message)
          system.config.assertions);
      unit = builtins.hasAttr "tor-mullvad-bypass" system.config.systemd.services;
    };
in map check modes
""",
            {},
        )
        for result, expected in zip(
            results, ([False, False], [True, False], [False, True], [True, True])
        ):
            with self.subTest(expected=expected):
                by_message = {item["message"]: item["assertion"] for item in result["assertions"]}
                self.assertEqual(
                    by_message.get("Tor/Mullvad bypass requires services.tor.enable.", True),
                    expected[0],
                )
                self.assertEqual(
                    by_message.get(
                        "Tor/Mullvad bypass requires services.mullvad-vpn.enable.", True
                    ),
                    expected[1],
                )
                self.assertEqual(result["unit"], all(expected))


class BluetoothContracts(unittest.TestCase):
    def test_bluetooth_pairing_and_media_controls(self):
        result = evaluate(
            """
  lib = flake.inputs.nixpkgs.lib;
  system = lib.nixosSystem {
    system = builtins.currentSystem;
    modules = [ (root + "/modules/nixos/desktop/bluetooth.nix") {
      boot.isContainer = true;
      system.stateVersion = "26.05";
      services.pipewire.enable = true;
    } ];
  };
  config = system.config;
in {
  enabled = config.hardware.bluetooth.enable;
  powered = config.hardware.bluetooth.powerOnBoot;
  pairing = config.services.blueman.enable;
  media = config.services.pipewire.wireplumber.extraConfig
    ."51-bluetooth-media-controls"."monitor.bluez.properties"."bluez5.dummy-avrcp-player";
  proxy = builtins.hasAttr "mpris-proxy" config.systemd.user.services;
  settings = config.hardware.bluetooth.settings;
}
""",
            {},
        )
        for setting in ("enabled", "powered", "pairing", "media"):
            self.assertTrue(result[setting], setting)
        self.assertFalse(result["proxy"], "mpris-proxy conflicts with WirePlumber AVRCP")
        self.assertNotIn("DeviceID", result["settings"].get("General", {}))

    def test_librepods_capability_is_restricted_to_configured_account(self):
        result = evaluate(
            """
  lib = flake.inputs.nixpkgs.lib;
  pkgs = flake.inputs.nixpkgs.legacyPackages.${builtins.currentSystem};
  fixture = pkgs.hello;
  system = lib.nixosSystem {
    system = builtins.currentSystem;
    specialArgs = {
      librepodsPackage = fixture;
      setup.username = "bluetooth-fixture";
    };
    modules = [ (root + "/modules/nixos/desktop/librepods.nix") {
      boot.isContainer = true;
      system.stateVersion = "26.05";
      users.users.bluetooth-fixture.isNormalUser = true;
    } ];
  };
in {
  wrapper = system.config.security.wrappers.librepods;
  groups = system.config.users.users.bluetooth-fixture.extraGroups;
  groupExists = builtins.hasAttr "librepods" system.config.users.groups;
  packageInstalled = builtins.elem fixture system.config.environment.systemPackages;
  expectedSource = lib.getExe fixture;
}
""",
            {},
        )
        wrapper = result["wrapper"]
        self.assertEqual(wrapper["capabilities"], "cap_net_admin+ep")
        self.assertEqual(wrapper["source"], result["expectedSource"])
        self.assertEqual(wrapper["owner"], "root")
        self.assertEqual(wrapper["group"], "librepods")
        self.assertEqual(wrapper["permissions"], "u+rx,g+x")
        self.assertFalse(wrapper["setuid"])
        self.assertFalse(wrapper["setgid"])
        self.assertTrue(result["groupExists"])
        self.assertTrue(result["packageInstalled"])
        self.assertIn("librepods", result["groups"])

    def test_librepods_login_service_uses_wrapper_and_graphical_lifecycle(self):
        service = evaluate(
            """
  lib = flake.inputs.nixpkgs.lib;
  pkgs = flake.inputs.nixpkgs.legacyPackages.${builtins.currentSystem};
in (import (root + "/home-manager/modules/desktop-apps/librepods.nix") { inherit lib pkgs; })
  .systemd.user.services.librepods
""",
            {},
        )
        self.assertEqual(
            service["Service"]["ExecStart"], "/run/wrappers/bin/librepods --start-minimized"
        )
        self.assertEqual(
            service["Unit"]["ConditionPathIsExecutable"], "/run/wrappers/bin/librepods"
        )
        self.assertEqual(service["Unit"]["PartOf"], ["graphical-session.target"])
        self.assertEqual(service["Install"]["WantedBy"], ["graphical-session.target"])
        self.assertEqual(service["Service"]["Restart"], "on-failure")

    def test_librepods_indicator_preserves_extensions_and_is_idempotent(self):
        hook = evaluate(
            """
  pkgs = flake.inputs.nixpkgs.legacyPackages.${builtins.currentSystem};
  lib = pkgs.lib // { hm.dag.entryAfter = _: script: script; };
in (import (root + "/home-manager/modules/desktop-apps/librepods.nix") { inherit lib pkgs; })
  .home.activation.enableLibrePodsIndicator
""",
            {},
        )
        script = hook.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        with tempfile.TemporaryDirectory(prefix="indicator-test-") as directory:
            root = Path(directory)
            state = root / "extensions.json"
            gsettings = root / "gsettings"
            gsettings.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "p = Path(os.environ['EXTENSION_FIXTURE'])\n"
                "if sys.argv[1] == 'get': print(json.loads(p.read_text())['value'])\n"
                "else:\n"
                " data = json.loads(p.read_text())\n"
                " data['value'] = sys.argv[-1]; data['writes'] += 1\n"
                " p.write_text(json.dumps(data))\n"
            )
            gsettings.chmod(0o700)
            for initial in ("['existing-theme@example.test']", "@as []"):
                with self.subTest(initial=initial):
                    state.write_text(json.dumps({"value": initial, "writes": 0}))
                    for _ in range(2):
                        subprocess.run(
                            ["python3", "-c", script, str(gsettings), "indicator@example.test"],
                            env=dict(os.environ, EXTENSION_FIXTURE=str(state)),
                            check=True,
                            timeout=10,
                        )
                    result = json.loads(state.read_text())
                    self.assertEqual(result["writes"], 1)
                    enabled = ast.literal_eval(result["value"])
                    expected = ast.literal_eval(initial.removeprefix("@as "))
                    self.assertEqual(enabled, expected + ["indicator@example.test"])


class SkillsActivation(unittest.TestCase):
    def test_activation_keeps_order_and_uses_only_local_installer(self):
        with tempfile.TemporaryDirectory(prefix="skills-activation-test-") as directory:
            root = Path(directory)
            activation = evaluate(
                """
  packages = flake.inputs.nixpkgs.legacyPackages.${builtins.currentSystem};
  lib = packages.lib // { hm.dag.entryAfter = after: data: { inherit after data; }; };
  pkgs = packages // { runCommand = _: _: _: builtins.getEnv "CONFIG_TEST_BUNDLE"; };
  aiPackages.skills = { type = "derivation"; name = "skills";
    outPath = builtins.getEnv "CONFIG_TEST_CLI"; meta.mainProgram = "skills"; };
in (import (root + "/home-manager/modules/ai/skills.nix") { inherit lib pkgs aiPackages; })
  .home.activation.installAgentSkills
""",
                {
                    "CONFIG_TEST_BUNDLE": str(root / "nonexistent bundle"),
                    "CONFIG_TEST_CLI": str(root / "nonexistent-cli"),
                },
            )
            self.assertEqual(activation["after"], ["linkGeneration"])
            result = subprocess.run(
                ["bash", "-e", "-c", activation["data"]],
                env=dict(os.environ, HOME=str(root), DRY_RUN="1"),
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Would sync prepared", result.stdout)
            self.assertEqual(list(root.iterdir()), [])
            self.assertNotIn("git", activation["data"])
            self.assertNotIn("https://", activation["data"])
            bundle = root / "nonexistent bundle"
            source = bundle / "source-0"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("fixture")
            (bundle / "manifest.json").write_text(
                json.dumps([{"directory": "source-0", "skill": "fixture", "url": "fixture"}])
            )
            cli = root / "nonexistent-cli/bin/skills"
            cli.parent.mkdir(parents=True)
            cli.write_text(
                f"#!{sys.executable}\nimport json, os, sys\nfrom pathlib import Path\n"
                "Path(os.environ['ACTIVATION_LOG']).write_text(json.dumps(sys.argv[1:]))\n"
            )
            cli.chmod(0o700)
            log = root / "installer-arguments"
            environment = {key: value for key, value in os.environ.items() if key != "DRY_RUN"}
            environment.update(HOME=str(root), ACTIVATION_LOG=str(log))
            result = subprocess.run(
                ["bash", "-e", "-c", activation["data"]],
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            arguments = json.loads(log.read_text())
            self.assertEqual(arguments[0], "add")
            self.assertFalse(Path(arguments[1]).exists(), "Writable staging must be cleaned")
            self.assertEqual(
                arguments[2:], ["--global", "--agent", "*", "--skill", "fixture", "--yes"]
            )


class DesktopArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("tmux", "niri"):
            if not shutil.which(tool):
                raise RuntimeError(f"Managed {tool} is required for generated-config validation")
        cls.temporary = tempfile.TemporaryDirectory(prefix="desktop-config-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.config_home = cls.root / "config with $dollar and 'quote"
        selection = subprocess.run(
            ["bash", "-c", 'source scripts/config.sh; select_home; printf "%s" "$HOME_CONFIG"'],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        cls.generated = evaluate(
            """
  home = flake.homeConfigurations.${builtins.getEnv "CONFIG_TEST_OUTPUT"};
  custom = home.extendModules { modules = [{ xdg.configHome = builtins.getEnv "CONFIG_TEST_HOME"; }]; };
  niriFor = monitors: (import (root + "/home-manager/modules/desktop/niri.nix") {
    inherit (home) pkgs;
    inherit (home) config;
    lib = flake.inputs.nixpkgs.lib;
    aiPackages = flake.inputs.llm-agents.packages.${builtins.currentSystem};
    setup = {
      inherit monitors;
      keyboard = { layouts = [ "us" ]; toggle = "grp:caps_toggle"; };
    };
  }).xdg.configFile."niri/config.kdl".text;
in {
  niri = home.config.xdg.configFile."niri/config.kdl".text;
  niriAutomatic = niriFor [];
  niriMultiple = niriFor [
    {
      match = "Fixture Portrait";
      mode = "1920x1080@120.000";
      scale = 1;
      transform = "90";
      position = { x = 2560; y = -420; };
      primary = false;
    }
    {
      match = "Fixture Main";
      mode = "2560x1080@74.991";
      scale = 1;
      transform = "normal";
      position = { x = 0; y = 0; };
      primary = true;
    }
  ];
  tmux = custom.config.programs.tmux.extraConfig;
  mimeDefaults = home.config.xdg.mimeApps.defaultApplications;
}
""",
            {"CONFIG_TEST_OUTPUT": selection.stdout, "CONFIG_TEST_HOME": str(cls.config_home)},
        )

    def test_niri_configuration_is_accepted(self):
        for name in ("niri", "niriAutomatic", "niriMultiple"):
            with self.subTest(config=name):
                config = self.root / f"{name}.kdl"
                config.write_text(self.generated[name])
                result = subprocess.run(
                    ["niri", "validate", "--config", str(config)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_niri_multiple_outputs_and_primary_startup(self):
        config = self.generated["niriMultiple"]
        portrait = config.split('output "Fixture Portrait" {', 1)[1].split("}", 1)[0]
        main = config.split('output "Fixture Main" {', 1)[1].split("}", 1)[0]
        self.assertIn('mode "1920x1080@120.000"', portrait)
        self.assertIn('transform "90"', portrait)
        self.assertIn("position x=2560 y=-420", portrait)
        self.assertNotIn("focus-at-startup", portrait)
        self.assertIn("scale 1", main)
        self.assertIn("position x=0 y=0", main)
        self.assertIn("focus-at-startup", main)
        self.assertEqual(config.count('open-on-output "Fixture Main"'), 4)
        self.assertNotIn('open-on-output "Fixture Portrait"', config)

    def test_niri_automatic_outputs_have_no_fixed_placement(self):
        config = self.generated["niriAutomatic"]
        self.assertNotIn("\noutput ", config)
        self.assertNotIn("focus-at-startup", config)
        self.assertNotIn("open-on-output", config)
        self.assertIn('workspace "1" {', config)

    def test_niri_monitor_shortcuts_and_named_workspaces(self):
        config = self.generated["niri"]
        for key, direction in (("Left", "left"), ("Right", "right"), ("H", "left"), ("L", "right")):
            self.assertIn(f"Mod+Shift+{key} {{ move-window-to-monitor-{direction}; }}", config)
            self.assertIn(f"Mod+Ctrl+{key} {{ move-column-{direction}; }}", config)
        for key, direction in (("Left", "left"), ("Right", "right")):
            self.assertIn(f"Mod+Alt+{key} {{ focus-monitor-{direction}; }}", config)
            self.assertIn(f"Mod+Shift+Ctrl+{key} {{ move-column-to-monitor-{direction}; }}", config)
        for index in range(1, 5):
            self.assertIn(f'Mod+{index} {{ focus-workspace "{index}"; }}', config)
            self.assertIn(f'Mod+Shift+{index} {{ move-window-to-workspace "{index}"; }}', config)
            self.assertIn(f'Mod+Ctrl+{index} {{ move-column-to-workspace "{index}"; }}', config)

    def test_xdg_open_routes_local_files_and_web_links(self):
        # Run the real opener with generated MIME defaults but harmless fake
        # desktop launchers. No GUI apps or live user settings are touched.
        with tempfile.TemporaryDirectory(prefix="mime-routing-test-") as temporary:
            root = Path(temporary)
            config = root / "config"
            applications = root / "data/applications"
            config.mkdir()
            applications.mkdir(parents=True)
            defaults = self.generated["mimeDefaults"]
            (config / "mimeapps.list").write_text(
                "[Default Applications]\n"
                + "".join(f"{mime}={';'.join(apps)};\n" for mime, apps in defaults.items())
            )
            log = root / "opened.json"
            launcher = root / "launcher"
            launcher.write_text(
                f"#!{sys.executable}\nimport json, sys\nfrom pathlib import Path\n"
                f"Path({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
            )
            launcher.chmod(0o700)
            for desktop in {app for apps in defaults.values() for app in apps}:
                (applications / desktop).write_text(
                    "[Desktop Entry]\nType=Application\nName=Routing Fixture\n"
                    f"Exec={launcher} {desktop} %u\n"
                )
            fallback = root / "browser-fallback"
            fallback.write_text(f'#!/bin/sh\nexec "{launcher}" browser-fallback "$@"\n')
            fallback.chmod(0o700)
            # Keep only executable/locale/MIME-data discovery. Inherited KDE,
            # GNOME, portal or D-Bus settings must not select a live GUI backend.
            env = {
                key: os.environ[key]
                for key in ("PATH", "LANG", "LC_ALL", "XDG_DATA_DIRS")
                if key in os.environ
            }
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            env.update(
                HOME=str(root),
                XDG_CONFIG_HOME=str(config),
                XDG_CONFIG_DIRS=str(config),
                XDG_DATA_HOME=str(root / "data"),
                XDG_RUNTIME_DIR=str(runtime),
                XDG_CURRENT_DESKTOP="X-Generic",
                DBUS_SESSION_BUS_ADDRESS=f"unix:path={runtime / 'no-session-bus'}",
                BROWSER=str(fallback),
                DISPLAY=":fixture",
            )
            samples = [
                ("folder with spaces", None, "org.gnome.Nautilus.desktop"),
                ("notes.txt", b"editable plain text\n", "code.desktop"),
                ("README.md", b"# Editable Markdown\n", "code.desktop"),
                ("settings.json", b'{"editable": true}\n', "code.desktop"),
                ("settings.yaml", b"editable: true\n", "code.desktop"),
                ("settings.toml", b"editable = true\n", "code.desktop"),
                ("module.nix", b"{ }: { editable = true; }\n", "code.desktop"),
                ("script.py", b"print('editable')\n", "code.desktop"),
                ("script.sh", b"#!/bin/sh\nprintf editable\n", "code.desktop"),
                ("main.rs", b"fn main() {}\n", "code.desktop"),
                ("query.sql", b"SELECT 1;\n", "code.desktop"),
                ("Program.cs", b"class Program {}\n", "code.desktop"),
                ("change.patch", b"--- a/file\n+++ b/file\n", "code.desktop"),
                ("table.csv", b"name,value\neditable,true\n", "code.desktop"),
                ("image.png", b"\x89PNG\r\n\x1a\n", "org.gnome.Loupe.desktop"),
                ("report.pdf", b"%PDF-1.7\n", "org.gnome.Papers.desktop"),
                ("audio.mp3", b"ID3\x04\x00\x00\x00\x00\x00\x00", "org.gnome.Decibels.desktop"),
                ("archive.zip", b"PK\x03\x04", "org.gnome.Nautilus.desktop"),
                ("page.html", b"<!doctype html><title>Fixture</title>\n", "firefox.desktop"),
            ]
            for name, content, expected in samples:
                target = root / name
                if content is None:
                    target.mkdir()
                else:
                    target.write_bytes(content)
                # Both raw paths and OSC 8 file URIs must use the file's MIME
                # type; a generic file-scheme browser handler is not a fix.
                for argument in (str(target), target.as_uri()):
                    with self.subTest(target=argument):
                        log.unlink(missing_ok=True)
                        subprocess.run(
                            ["xdg-open", argument],
                            env=env,
                            capture_output=True,
                            check=True,
                            timeout=10,
                        )
                        self.assertEqual(json.loads(log.read_text()), [expected, argument])
            log.unlink(missing_ok=True)
            subprocess.run(
                ["xdg-open", "https://example.com/issue/386"],
                env=env,
                capture_output=True,
                check=True,
                timeout=10,
            )
            self.assertEqual(
                json.loads(log.read_text()), ["firefox.desktop", "https://example.com/issue/386"]
            )

    def test_tmux_preserves_ghostty_labelled_web_and_file_links(self):
        # Exercise tmux's actual terminal output, not capture-pane (which can
        # retain link metadata even when tmux strips it before Ghostty sees it).
        with tempfile.TemporaryDirectory(prefix="tmux-links-test-") as temporary:
            root = Path(temporary)
            command = ["tmux", "-S", str(root / "tmux.sock")]
            env = {
                key: value
                for key, value in os.environ.items()
                if key not in {"TMUX", "TMUX_PANE"} and not key.startswith("HERDR_")
            }
            env.update(HOME=str(root), TERM="xterm-ghostty")
            config = root / "tmux.conf"
            config.write_text(self.generated["tmux"] + "\nset -g mouse on\n")
            urls = ("https://example.com/issue/386", (root / "file with spaces.txt").as_uri())
            payload = (
                "".join(
                    f"\x1b]8;;{url}\x1b\\Label {index}\x1b]8;;\x1b\\\r\n"
                    for index, url in enumerate(urls)
                )
                + "LINK_FIXTURE_READY\r\n"
            )
            fixture = root / "fixture.py"
            fixture.write_text(f"import os\nos.write(1, {payload.encode()!r})\nos.read(0, 1)\n")
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))

            def controlling_terminal():
                os.setsid()
                fcntl.ioctl(0, termios.TIOCSCTTY, 0)

            process = None
            try:
                process = subprocess.Popen(
                    [
                        *command,
                        "-f",
                        str(config),
                        "new-session",
                        "-s",
                        "fixture",
                        shlex.join([sys.executable, str(fixture)]),
                    ],
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    env=env,
                    preexec_fn=controlling_terminal,
                )
                output = bytearray()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    readable, _, _ = select.select(
                        [master], [], [], max(0, deadline - time.monotonic())
                    )
                    if not readable:
                        break
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output.extend(chunk)
                    if b"LINK_FIXTURE_READY" in output:
                        break
                self.assertIn(b"LINK_FIXTURE_READY", output, "tmux fixture did not render")
                features = subprocess.check_output(
                    [*command, "list-clients", "-F", "#{client_termfeatures}"],
                    env=env,
                    text=True,
                    timeout=10,
                ).strip()
                # Pi uses this capability to decide whether to emit links.
                self.assertIn("hyperlinks", features.split(","))
                self.assertIn(b"\x1b]8;", output)
                for url in urls:
                    with self.subTest(url=url):
                        self.assertIn(url.encode(), output, "tmux stripped the link destination")
            finally:
                subprocess.run([*command, "kill-server"], env=env, capture_output=True, timeout=10)
                if process is not None:
                    process.wait(timeout=10)
                os.close(slave)
                os.close(master)

    def test_tmux_reload_uses_quoted_custom_xdg_path(self):
        socket = str(self.root / "tmux.sock")
        command = ["tmux", "-S", socket]
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"TMUX", "TMUX_PANE"} and not key.startswith("HERDR_")
        }
        env["HOME"] = str(self.root)
        subprocess.run(
            [*command, "-f", "/dev/null", "new-session", "-d", "-s", "fixture", "sleep 60"],
            env=env,
            check=True,
            capture_output=True,
            timeout=10,
        )
        try:
            config = self.root / "tmux.conf"
            config.write_text(self.generated["tmux"])
            subprocess.run(
                [*command, "source-file", str(config)],
                env=env,
                check=True,
                capture_output=True,
                timeout=10,
            )
            binding = subprocess.run(
                [*command, "list-keys", "-T", "prefix", "r"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            expected = self.config_home / "tmux/tmux.conf"
            expected.parent.mkdir(parents=True)
            expected.write_text("set -g @reload-fixture accepted\n")
            # Replay the stored binding through tmux's parser, not a shell parser.
            # The two grammars treat escaped dollars inside quotes differently.
            _, separator, reload_command = binding.stdout.partition(" r ")
            self.assertTrue(separator, binding.stdout)
            reload = self.root / "reload.conf"
            reload.write_text(reload_command.replace(r"\;", ";"))
            subprocess.run(
                [*command, "source-file", str(reload)],
                env=env,
                check=True,
                capture_output=True,
                timeout=10,
            )
            marker = subprocess.run(
                [*command, "show-options", "-gv", "@reload-fixture"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(marker.stdout.strip(), "accepted")
        finally:
            subprocess.run([*command, "kill-server"], env=env, capture_output=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
