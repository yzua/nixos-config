#!/usr/bin/env python3
"""On-demand TV intent, private token and transport lifecycle tests; never use a TV."""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "home-manager/modules/ai/pi-home/tv.py"
spec = importlib.util.spec_from_file_location("pi_home_tv", CODE)
tv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tv)


class HandshakeBase:
    def __init__(self, **kwargs):
        vars(self).update(kwargs)
        self.connection = None
        self.endpoint = "samsung.remote.control"

    def _format_websocket_url(self, endpoint):
        return f"wss://{self.host}:8002/{endpoint}?token=FAKE_TOKEN"

    def _check_for_token(self, response):
        self.token = response.get("data", {}).get("token")


class HandshakeSocket:
    def __init__(self, status=101):
        self.status = status
        self.closed = False
        self.reads = 0

    def getstatus(self):
        return self.status

    def recv(self):
        self.reads += 1
        return '{"event":"ms.channel.clientConnect"}'

    def shutdown(self):
        self.closed = True


class TV(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pi-home-tv-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = {"HOME": str(self.root), "XDG_STATE_HOME": str(self.root / "state")}
        self.config = {"host": "192.168.20.30", "apps": {"player": "fixture.Player"}}
        self.calls = []
        self.remote = self
        self.token = "NEW-PAIRING-CANARY"
        self.kwargs = None

    def factory(self, **kwargs):
        self.kwargs = kwargs
        self.calls.append("construct")
        return self.remote

    def open(self):
        self.calls.append("open")

    def close(self):
        self.calls.append("close")

    def send_key(self, key):
        self.calls.append(("key", key))

    def run_app(self, app):
        self.calls.append(("app", app))

    def run_command(self, command="connect", **kwargs):
        args = argparse.Namespace(
            command=command, execute=False, key="pause", app="player", level=None
        )
        vars(args).update(kwargs)
        return tv.run(self.config, args, self.env, self.factory)

    def test_connect_authorizes_without_buttons_and_saves_private_token(self):
        result = self.run_command()
        self.assertEqual(self.calls, ["construct", "open", "close"])
        self.assertEqual(result["status"], "authorized")
        self.assertNotIn("CANARY", json.dumps(result))
        token = tv.token_path(self.env)
        self.assertEqual(token.read_text(), self.token)
        self.assertEqual(token.stat().st_mode & 0o777, 0o600)
        self.assertEqual(token.parent.stat().st_mode & 0o777, 0o700)
        self.assertIsNone(self.kwargs["token"])
        self.assertEqual(self.kwargs["port"], 8002)
        self.assertNotIn("token_file", self.kwargs)

    def test_saved_pairing_and_execute_are_required_before_an_action(self):
        for command in ("key", "launch"):
            with self.assertRaisesRegex(ValueError, "--execute"):
                self.run_command(command)
            with self.assertRaisesRegex(ValueError, "Pair first"):
                self.run_command(command, execute=True)
        self.assertEqual(self.calls, [])

    def test_exactly_one_allowed_action_and_socket_close_per_invocation(self):
        self.run_command()
        self.calls.clear()
        result = self.run_command("key", execute=True)
        self.assertEqual(self.calls, ["construct", "open", ("key", "KEY_PAUSE"), "close"])
        self.assertEqual(self.kwargs["token"], self.token)
        self.assertEqual(result["status"], "sent")
        self.calls.clear()
        self.run_command("launch", execute=True)
        self.assertEqual(self.calls, ["construct", "open", ("app", "fixture.Player"), "close"])

    def test_volume_read_is_non_mutating_and_needs_no_pairing(self):
        with patch.object(tv, "volume_request", return_value=50) as request:
            result = self.run_command("volume")
        self.assertEqual(result["volume"], 50)
        request.assert_called_once_with(self.config["host"], "GetVolume")
        self.assertEqual(self.calls, [])
        self.assertFalse(tv.token_path(self.env).parent.exists())

    def test_exact_volume_requires_intent_pairing_and_verified_readback(self):
        for level in (-1, 101, True, "100"):
            with self.assertRaisesRegex(ValueError, "0.*100"):
                self.run_command("volume", level=level, execute=True)
        with self.assertRaisesRegex(ValueError, "--execute"):
            self.run_command("volume", level=100)
        with self.assertRaisesRegex(ValueError, "Pair first"):
            self.run_command("volume", level=100, execute=True)
        self.run_command()
        self.calls.clear()
        with patch.object(tv, "volume_request", side_effect=[50, None, 100]) as request:
            result = self.run_command("volume", level=100, execute=True)
        self.assertEqual(self.calls, ["construct", "open", "close"])
        self.assertEqual(
            [call.args[1:] for call in request.call_args_list],
            [("GetVolume",), ("SetVolume", 100), ("GetVolume",)],
        )
        self.assertEqual(
            (result["status"], result["previous"], result["volume"]), ("verified", 50, 100)
        )
        with patch.object(tv, "volume_request", side_effect=[100]) as request:
            self.run_command("volume", level=100, execute=True)
        self.assertEqual(request.call_count, 1)
        with patch.object(tv, "volume_request", side_effect=[50, None, 50]) as request:
            with self.assertRaisesRegex(ValueError, "read-back"):
                self.run_command("volume", level=100, execute=True)
        self.assertEqual(request.call_count, 3)

    def test_volume_soap_is_narrow_bounded_and_sanitizes_invalid_responses(self):
        class Response:
            def __init__(self, data):
                self.data = data

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def read(self, size):
                self.size = size
                return self.data[:size]

        valid = b"<Envelope><GetVolumeResponse><CurrentVolume>50</CurrentVolume></GetVolumeResponse></Envelope>"
        response = Response(valid)
        with patch.object(tv.urllib.request, "build_opener") as builder:
            builder.return_value.open.return_value = response
            self.assertEqual(tv.volume_request(self.config["host"], "GetVolume"), 50)
        request = builder.return_value.open.call_args.args[0]
        self.assertEqual(
            request.full_url, f"http://{self.config['host']}:9197/upnp/control/RenderingControl1"
        )
        self.assertIn(b"<u:GetVolume", request.data)
        self.assertNotIn(b"DesiredVolume", request.data)
        self.assertEqual(response.size, 65537)
        self.assertIsInstance(builder.call_args.args[0], tv.urllib.request.ProxyHandler)
        self.assertEqual(builder.call_args.args[0].proxies, {})
        self.assertIsInstance(builder.call_args.args[1], tv.NoRedirect)
        with patch.object(tv.urllib.request, "build_opener") as builder:
            builder.return_value.open.return_value = Response(
                b"<Envelope><SetVolumeResponse/></Envelope>"
            )
            tv.volume_request(self.config["host"], "SetVolume", 100)
        self.assertIn(
            b"<DesiredVolume>100</DesiredVolume>", builder.return_value.open.call_args.args[0].data
        )
        self.assertNotIn(b"SetMute", builder.return_value.open.call_args.args[0].data)
        entity = '<!DOCTYPE x [<!ENTITY v "50">]><GetVolumeResponse><CurrentVolume>&v;</CurrentVolume></GetVolumeResponse>'
        for malformed in (
            b"<Fault>SECRET-CANARY</Fault>",
            b"<!DOCTYPE x><x/>",
            b"x" * 65537,
            b"<x>",
            valid.replace(b">50<", b">101<"),
            *(entity.encode(encoding) for encoding in ("utf-16", "utf-16-le", "utf-16-be")),
        ):
            with patch.object(tv.urllib.request, "build_opener") as builder:
                builder.return_value.open.return_value = Response(malformed)
                with self.assertRaises(tv.ControlError) as error:
                    tv.volume_request(self.config["host"], "GetVolume")
                self.assertNotIn("CANARY", str(error.exception))
        for action in ("SetMute", "Play", "SetAVTransportURI"):
            with self.assertRaises(tv.ControlError):
                tv.volume_request(self.config["host"], action)

    def test_raw_service_keys_unknown_apps_and_non_lan_hosts_are_refused(self):
        for command, extra in (("key", {"key": "KEY_FACTORY"}), ("launch", {"app": "foreign"})):
            with self.assertRaises(ValueError):
                self.run_command(command, execute=True, **extra)
        for host in ("example.invalid", "8.8.8.8", "127.0.0.1", "0.0.0.0", "169.254.1.2", "::1"):
            self.config["host"] = host
            with self.assertRaises(ValueError):
                self.run_command()
        self.assertEqual(self.calls, [])

    def test_info_does_not_pair_or_create_token_state(self):
        with patch.object(tv, "device_info", return_value={"modelName": "fixture"}) as info:
            self.assertEqual(self.run_command("info"), {"modelName": "fixture"})
        info.assert_called_once_with(self.config["host"])
        self.assertFalse(tv.token_path(self.env).parent.exists())
        self.assertEqual(self.calls, [])

    def test_symlink_and_hardlink_token_targets_are_refused(self):
        token = tv.token_path(self.env)
        token.parent.mkdir(parents=True)
        other = self.root / "other"
        other.write_text("KEEP-CANARY")
        for kind in ("symlink", "hardlink"):
            if kind == "symlink":
                token.symlink_to(other)
            else:
                os.link(other, token)
            with self.assertRaises(ValueError):
                self.run_command()
            self.assertEqual(other.read_text(), "KEEP-CANARY")
            token.unlink()
        self.assertEqual(self.calls, [])

    def test_transport_failure_closes_without_retry(self):
        with patch.object(self, "open", side_effect=RuntimeError("URL-AND-TOKEN-CANARY")):
            with self.assertRaises(RuntimeError):
                self.run_command()
        self.assertEqual(self.calls, ["construct", "close"])

    def test_cli_help_has_no_device_or_state_effects(self):
        config = self.root / "tv.json"
        config.write_text(json.dumps(self.config))
        result = subprocess.run(
            [sys.executable, str(CODE), str(config), "--help"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("connect", result.stdout)
        self.assertFalse(tv.token_path(self.env).parent.exists())

    def test_handshake_redirect_is_refused_without_a_second_connection(self):
        socket = HandshakeSocket(status=302)
        calls = []

        def connector(url, **kwargs):
            calls.append((url, kwargs))
            return socket

        self.remote = tv.scoped_remote(HandshakeBase, connector)
        args = argparse.Namespace(command="connect")
        with self.assertRaisesRegex(ValueError, "redirects are disabled"):
            tv.run(self.config, args, self.env, self.remote)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["redirect_limit"], 0)
        self.assertEqual(calls[0][1]["http_no_proxy"], [self.config["host"]])
        self.assertEqual(socket.reads, 0)
        self.assertTrue(socket.closed)

    def test_continuous_startup_events_hit_overall_deadline_and_release_lock(self):
        socket = HandshakeSocket()
        factory = tv.scoped_remote(HandshakeBase, lambda *_args, **_kwargs: socket)
        with tv.operation_deadline(0.03), self.assertRaisesRegex(ValueError, "deadline reached"):
            tv.run(self.config, argparse.Namespace(command="connect"), self.env, factory)
        self.assertGreater(socket.reads, 1)
        self.assertTrue(socket.closed)
        # The ordinary fake connection can immediately acquire the same control lock.
        self.run_command()
        self.assertEqual(self.calls, ["construct", "open", "close"])

    def test_actual_websocket_client_does_not_follow_a_fake_handshake_redirect(self):
        try:
            import websocket
        except ImportError:
            self.skipTest("Run with the managed TV Python for the native transport adapter check")

        class RawSocket:
            def __init__(self):
                self.response = bytearray(
                    b"HTTP/1.1 302 Found\r\nLocation: wss://unconfigured.invalid/steal\r\nContent-Length: 0\r\n\r\n"
                )

            def gettimeout(self):
                return 1

            def settimeout(self, _timeout):
                pass

            def send(self, data):
                return len(data)

            def recv(self, size):
                data = self.response[:size]
                del self.response[:size]
                return bytes(data)

            def close(self):
                pass

        raw = RawSocket()

        def connect(*_args, **_kwargs):
            return raw, ("fixture", 8002, "/")

        with patch("websocket._core.connect", side_effect=connect) as connections:
            factory = tv.scoped_remote(HandshakeBase, websocket.create_connection)
            with self.assertRaisesRegex(ValueError, "redirects are disabled"):
                tv.run(self.config, argparse.Namespace(command="connect"), self.env, factory)
        self.assertEqual(connections.call_count, 1)

    def test_upstream_value_errors_are_sanitized_not_printed_as_validation_errors(self):
        config = self.root / "tv.json"
        config.write_text(json.dumps(self.config))
        with (
            patch.object(sys, "argv", [str(CODE), str(config), "connect"]),
            patch.object(tv, "run", side_effect=ValueError("TOKEN-URL-CANARY")),
            patch.dict(os.environ, self.env),
            contextlib.redirect_stderr(io.StringIO()) as output,
        ):
            with self.assertRaises(SystemExit):
                tv.main()
        self.assertNotIn("CANARY", output.getvalue())
        self.assertIn("No automatic retry", output.getvalue())


if __name__ == "__main__":
    unittest.main()
