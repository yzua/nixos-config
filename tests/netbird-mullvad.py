#!/usr/bin/env python3
"""Exercise the private firewall lifecycle without privileges or live networking."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modules/nixos/networking/netbird-mullvad-private.py"


class PrivateFirewall(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="netbird-mullvad-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.secret = self.root / "endpoint"
        self.secret.write_text("192.0.2.10\n")
        self.state = self.root / "runtime"
        self.calls = self.root / "calls.jsonl"
        self.nft = self.root / "nft"
        self.nft.write_text(
            "#!/usr/bin/env python3\n"
            "import json,os,sys\n"
            "text=sys.stdin.read()\n"
            "with open(os.environ['NFT_CALLS'],'a') as f:\n"
            " f.write(json.dumps({'args':sys.argv[1:],'rules':text})+'\\n')\n"
            "if os.environ.get('NFT_FAIL') in ('all', 'check' if '--check' in sys.argv else 'apply'):\n"
            " print(text,file=sys.stderr);sys.exit(1)\n"
        )
        self.nft.chmod(0o755)

    def run_action(
        self, action="apply", interface="mesh-fixture", https=None, routed=None, **environment
    ):
        return subprocess.run(
            [
                "python3",
                "-B",
                str(SCRIPT),
                action,
                interface,
                str(self.secret),
                str(self.state),
                str(self.nft),
            ]
            + ([str(https)] if https is not None else [])
            + (["--routed-https-secret", str(routed)] if routed is not None else []),
            env=dict(os.environ, NFT_CALLS=str(self.calls), **environment),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def transactions(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_apply_is_checked_atomic_and_confined_to_the_overlay_and_ports(self):
        result = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.transactions()
        self.assertEqual(calls[0]["args"], ["--check", "--file", "-"])
        self.assertEqual(calls[1]["args"], ["--file", "-"])
        self.assertEqual(calls[0]["rules"], calls[1]["rules"])
        text = calls[1]["rules"]
        self.assertIn("ip daddr 192.0.2.10 udp dport 53 counter", text)
        self.assertIn("ip daddr 192.0.2.10 tcp dport { 53, 443 } counter", text)
        self.assertIn('oifname != "mesh-fixture"', text)
        self.assertIn("ct mark 0x00000f41 drop", text)
        self.assertIn("type route hook output priority -110", text)
        self.assertIn("hook postrouting priority -100", text)
        marking, rest = text.split("  chain restore {", 1)
        restore, rest = rest.split("  chain guard {", 1)
        guard, _revoked = rest.split("  chain revoked {", 1)
        self.assertNotIn("oifname", marking, "initial output interface can still be Mullvad")
        self.assertEqual(marking.count("meta mark set 0x6d6f6c65"), 2)
        self.assertIn("hook postrouting priority -125", restore)
        self.assertIn('oifname "mesh-fixture"', restore)
        self.assertEqual(restore.count("meta mark 0x6d6f6c65 counter ct mark set 0x00000f41"), 2)
        self.assertNotIn("mark set", guard)
        self.assertNotIn("accept", guard.split("policy accept;", 1)[1])
        self.assertNotIn("skuid", text)
        self.assertNotIn("hook input", text)
        self.assertLess(text.index("priority -110"), text.index("priority -100"))
        self.assertEqual((self.state / "endpoints.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_revoke_uses_retained_state_not_the_current_secret(self):
        self.assertEqual(self.run_action().returncode, 0)
        self.secret.unlink()
        result = self.run_action("revoke")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.transactions()[-1]["rules"]
        self.assertNotIn("ct mark set", text)
        self.assertNotIn("oifname", text)
        self.assertIn("ip daddr 192.0.2.10 udp dport 53 ct mark 0x00000f41 drop", text)
        self.assertNotIn("meta mark set", text)
        revoked = text.split("  chain revoked {", 1)[1]
        self.assertIn("hook output priority -100", revoked)
        self.assertIn("ip daddr 192.0.2.10 udp dport 53 ct mark 0x00000f41 drop", revoked)
        self.assertIn("chain marking", text)
        self.assertTrue((self.state / "endpoints.json").exists())

    def test_endpoint_rotation_keeps_old_flow_guards(self):
        self.assertEqual(self.run_action().returncode, 0)
        self.secret.write_text("192.0.2.11\n")
        self.assertEqual(self.run_action().returncode, 0)
        text = self.transactions()[-1]["rules"]
        self.assertIn("ip daddr 192.0.2.11 udp dport 53 counter", text)
        self.assertIn('oifname != "mesh-fixture" ip daddr 192.0.2.11', text)
        self.assertIn("    ip daddr 192.0.2.10 udp dport 53 ct mark 0x00000f41 drop", text)
        self.assertNotIn("ip daddr 192.0.2.10 udp dport 53 counter", text)

    def test_failed_activation_retains_union_and_does_not_log_sensitive_diagnostics(self):
        self.assertEqual(self.run_action().returncode, 0)
        self.secret.write_text("192.0.2.11\n")
        result = self.run_action(NFT_FAIL="apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("192.0.2.", result.stderr + result.stdout)
        self.assertEqual(
            json.loads((self.state / "endpoints.json").read_text()),
            {"gateways": ["192.0.2.10", "192.0.2.11"], "https": [], "routed_https": []},
        )
        self.assertEqual(self.run_action("revoke").returncode, 0)
        text = self.transactions()[-1]["rules"]
        self.assertIn("ip daddr 192.0.2.10", text)
        self.assertIn("ip daddr 192.0.2.11", text)
        self.assertNotIn("ct mark set", text)

    def test_failed_syntax_check_does_not_apply(self):
        result = self.run_action(NFT_FAIL="check")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.transactions()), 1)
        self.assertNotIn("192.0.2.", result.stderr + result.stdout)

    def test_invalid_secret_and_interface_fail_without_printing_input(self):
        for value in ("invalid-private-value", "8.8.8.8", "127.0.0.1", "0.0.0.0", "169.254.1.1"):
            with self.subTest(kind="endpoint"):
                self.secret.write_text(value)
                result = self.run_action()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(value, result.stderr + result.stdout)
                self.assertFalse(self.calls.exists())
        self.secret.write_text("192.0.2.10")
        result = self.run_action(interface='mesh"; invalid')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("invalid", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_https_overlay_scope_rotation_and_revoke(self):
        https = self.root / "https-endpoint"
        https.write_text("100.64.0.10")
        self.assertEqual(self.run_action(https=https).returncode, 0)
        text = self.transactions()[-1]["rules"]
        self.assertIn("ip daddr 100.64.0.10 tcp dport 443 counter", text)
        self.assertIn('oifname != "mesh-fixture" ip daddr 100.64.0.10 tcp dport 443', text)
        self.assertNotIn("ip daddr 100.64.0.10 udp", text)
        self.assertNotIn("ip daddr 100.64.0.10 tcp dport 53", text)
        https.write_text("100.64.0.11")
        self.assertEqual(self.run_action(https=https).returncode, 0)
        text = self.transactions()[-1]["rules"]
        self.assertIn("    ip daddr 100.64.0.10 tcp dport 443 ct mark 0x00000f41 drop", text)
        https.unlink()
        self.secret.unlink()
        self.assertEqual(self.run_action("revoke", https=https).returncode, 0)
        text = self.transactions()[-1]["rules"]
        self.assertNotIn("ct mark set", text)
        self.assertNotIn("oifname", text)
        self.assertIn("ip daddr 100.64.0.11 tcp dport 443", text)

    def test_legacy_state_and_gateway_to_https_transition_keep_port_guards(self):
        self.state.mkdir(mode=0o700)
        (self.state / "endpoints.json").write_text('["192.0.2.11"]')
        https = self.root / "https-endpoint"
        https.write_text("192.0.2.11")
        self.assertEqual(self.run_action(https=https).returncode, 0)
        text = self.transactions()[-1]["rules"]
        self.assertIn('oifname != "mesh-fixture" ip daddr 192.0.2.11 tcp dport 443', text)
        self.assertIn("    ip daddr 192.0.2.11 tcp dport 53 ct mark 0x00000f41 drop", text)
        self.assertIn("    ip daddr 192.0.2.11 udp dport 53 ct mark 0x00000f41 drop", text)
        state = json.loads((self.state / "endpoints.json").read_text())
        self.assertIn("192.0.2.11", state["gateways"])
        self.assertIn("192.0.2.11", state["https"])

    def test_invalid_https_secret_does_not_install_partial_gateway_rules(self):
        https = self.root / "https-endpoint"
        https.write_text("8.8.8.8")
        result = self.run_action(https=https)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("8.8.8.8", result.stdout + result.stderr)
        self.assertFalse(self.calls.exists())

    def test_public_routed_https_is_exact_port_guarded_rotatable_and_revocable(self):
        routed = self.root / "routed-https"
        routed.write_text("93.184.216.34")
        result = self.run_action(routed=routed)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.transactions()[-1]["rules"]
        self.assertIn("ip daddr 93.184.216.34 tcp dport 443 counter", text)
        self.assertIn('oifname "mesh-fixture" ip daddr 93.184.216.34 tcp dport 443', text)
        self.assertIn('oifname != "mesh-fixture" ip daddr 93.184.216.34 tcp dport 443', text)
        self.assertNotIn("ip daddr 93.184.216.34 udp", text)
        self.assertNotIn("ip daddr 93.184.216.34 tcp dport 53", text)
        routed.write_text("93.184.216.35")
        self.assertEqual(self.run_action(routed=routed).returncode, 0)
        text = self.transactions()[-1]["rules"]
        self.assertIn("ip daddr 93.184.216.35 tcp dport 443 counter", text)
        self.assertIn("ip daddr 93.184.216.34 tcp dport 443 ct mark 0x00000f41 drop", text)
        self.assertNotIn("ip daddr 93.184.216.34 tcp dport 443 counter", text)
        state = json.loads((self.state / "endpoints.json").read_text())
        self.assertEqual(state["routed_https"], ["93.184.216.34", "93.184.216.35"])
        self.assertEqual(state["https"], [])
        routed.unlink()
        self.secret.unlink()
        self.assertEqual(self.run_action("revoke", routed=routed).returncode, 0)
        text = self.transactions()[-1]["rules"]
        self.assertNotIn("mark set", text)
        self.assertIn("ip daddr 93.184.216.35 tcp dport 443 ct mark 0x00000f41 drop", text)

    def test_public_scope_failure_retains_state_and_omission_revokes_without_secret_read(self):
        routed = self.root / "routed-https"
        routed.write_text("93.184.216.34")
        self.assertEqual(self.run_action(routed=routed).returncode, 0)
        routed.write_text("93.184.216.35")
        result = self.run_action(routed=routed, NFT_FAIL="apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("93.184.", result.stdout + result.stderr)
        state = json.loads((self.state / "endpoints.json").read_text())
        self.assertEqual(state["routed_https"], ["93.184.216.34", "93.184.216.35"])
        routed.unlink()
        self.assertEqual(self.run_action().returncode, 0)
        text = self.transactions()[-1]["rules"]
        for address in state["routed_https"]:
            self.assertIn(f"ip daddr {address} tcp dport 443 ct mark 0x00000f41 drop", text)
            self.assertNotIn(f"ip daddr {address} tcp dport 443 counter", text)
        self.assertIn("ip daddr 192.0.2.10 udp dport 53 counter", text)

    def test_routed_https_rejects_nonpublic_nonunicast_or_network_values(self):
        routed = self.root / "routed-https"
        for value in (
            "invalid",
            "10.0.0.1",
            "100.64.0.1",
            "192.0.2.1",
            "127.0.0.1",
            "169.254.1.1",
            "224.0.0.1",
            "240.0.0.1",
            "0.0.0.0",
            "::1",
            "8.8.8.8/32",
        ):
            with self.subTest(kind="routed HTTPS endpoint"):
                routed.write_text(value)
                result = self.run_action(routed=routed)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(value, result.stdout + result.stderr)
                self.assertFalse(self.calls.exists(), "validation must precede firewall changes")

    def test_repeated_apply_replaces_the_same_scoped_transaction(self):
        self.assertEqual(self.run_action().returncode, 0)
        first = self.transactions()[-1]["rules"]
        self.assertEqual(self.run_action().returncode, 0)
        self.assertEqual(self.transactions()[-1]["rules"], first)

    def test_revoke_before_first_activation_is_a_noop(self):
        self.secret.unlink()
        result = self.run_action("revoke")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.calls.exists())


class KernelRouting(unittest.TestCase):
    def test_scoped_policy_beats_mullvad_without_excluding_other_traffic(self):
        if not all(shutil.which(binary) for binary in ("unshare", "ip", "nft")):
            self.skipTest("requires unshare, ip, and nft in PATH")
        probe = subprocess.run(
            ["unshare", "--user", "--map-root-user", "--net", "true"],
            capture_output=True,
            check=False,
        )
        if probe.returncode:
            self.skipTest("unprivileged network namespaces unavailable")
        result = subprocess.run(
            [
                "unshare",
                "--user",
                "--map-root-user",
                "--net",
                "python3",
                "-B",
                str(ROOT / "tests/netbird-mullvad-routing.py"),
                str(Path("/proc/self/ns/net").readlink()),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
