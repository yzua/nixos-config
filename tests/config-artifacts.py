#!/usr/bin/env python3
"""Validate generated configs and activation/hooks using only isolated fixtures."""

import json
import os
import shutil
import subprocess
import tempfile
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
in {
  niri = home.config.xdg.configFile."niri/config.kdl".text;
  tmux = custom.config.programs.tmux.extraConfig;
}
""",
            {"CONFIG_TEST_OUTPUT": selection.stdout, "CONFIG_TEST_HOME": str(cls.config_home)},
        )

    def test_niri_configuration_is_accepted(self):
        config = self.root / "niri.kdl"
        config.write_text(self.generated["niri"])
        result = subprocess.run(
            ["niri", "validate", "--config", str(config)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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
