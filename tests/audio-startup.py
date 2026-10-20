#!/usr/bin/env python3
"""Offline regressions for the graph readiness gate used by EQ and shell startup."""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "audio_ready", ROOT / "home-manager/modules/desktop/audio-ready.py"
)
ready = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ready)


def graph(name="test-headset", channels=2):
    return [
        {
            "props": {"metadata.name": "default"},
            "metadata": [{"subject": 0, "key": "default.audio.sink", "value": {"name": name}}],
        },
        {
            "id": 70,
            "type": "PipeWire:Interface:Node",
            "info": {
                "props": {
                    "node.name": name,
                    "media.class": "Audio/Sink",
                    "device.id": 57,
                    "audio.channels": channels,
                }
            },
        },
        *[
            {
                "type": "PipeWire:Interface:Port",
                "info": {"props": {"node.id": 70, "port.direction": "in"}},
            }
            for _ in range(channels)
        ],
    ]


class AudioStartup(unittest.TestCase):
    def test_no_default_or_missing_device(self):
        self.assertFalse(ready.output_ready([]))
        self.assertFalse(ready.output_ready(graph()[1:]))
        self.assertFalse(ready.output_ready(graph()[:1]))

    def test_virtual_sink_is_not_ready(self):
        snapshot = graph("easyeffects_sink")
        del snapshot[1]["info"]["props"]["device.id"]
        self.assertFalse(ready.output_ready(snapshot))
        snapshot = graph()
        snapshot[1]["info"]["props"]["node.virtual"] = True
        self.assertFalse(ready.output_ready(snapshot))

    def test_waits_for_all_playback_ports(self):
        snapshot = graph()
        self.assertFalse(ready.output_ready(snapshot[:2]))
        self.assertFalse(ready.output_ready(snapshot[:3]))
        snapshot[-1]["info"]["props"]["port.direction"] = "out"
        self.assertFalse(ready.output_ready(snapshot))

    def test_headset_alternate_and_mono_outputs(self):
        for name, channels in (("test-headset", 2), ("test-hdmi", 2), ("test-mono", 1)):
            with self.subTest(name=name):
                self.assertTrue(ready.output_ready(graph(name, channels)))

    def test_enumeration_transition_and_timeout(self):
        checks = iter((False, False, True))
        with patch.object(ready.time, "sleep"):
            self.assertTrue(ready.wait_for_output(lambda: next(checks)))
        self.assertFalse(ready.wait_for_output(lambda: False, timeout=0))
        self.assertFalse(ready.wait_for_output(lambda: ready.output_ready(graph()[:2]), timeout=0))

    def test_server_errors_are_bounded(self):
        for error in (
            OSError("server not started"),
            subprocess.TimeoutExpired("pw-dump", 2),
            ValueError("incomplete JSON"),
        ):
            with self.subTest(error=error), patch.object(ready, "probe", side_effect=error):
                self.assertFalse(ready.wait_for_output(ready.probe, timeout=0))

    def test_probe_is_read_only_and_uses_real_dump_format(self):
        import json

        result = subprocess.CompletedProcess(["pw-dump"], 0, json.dumps(graph()))
        with patch.object(ready.subprocess, "run", return_value=result) as run:
            self.assertTrue(ready.probe())
            run.assert_called_once_with(
                ["pw-dump"], capture_output=True, text=True, check=True, timeout=2
            )


if __name__ == "__main__":
    unittest.main()
