#!/usr/bin/env python3
"""Check Pi initialization preserves private config and later user preferences."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("pi_initialize", ROOT / "home-manager/modules/ai/pi/initialize.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InitializeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.agent = self.root / "agent"
        self.agent.mkdir()
        self.state = self.root / "state"
        self.settings = {
            "defaultProvider": "test-provider",
            "defaultModel": "previous-model",
            "theme": "custom-theme",
            "extensions": ["custom-extension.ts", "+builtin:mcp"],
        }
        self.models = {"providers": {"test-provider": {
            "api": "openai-responses",
            "baseUrl": "https://endpoint.invalid/v1",
            "headers": {"X-Test": "private-example"},
            "models": [{"id": "previous-model", "contextWindow": 123456, "maxTokens": 12345}],
        }}}
        self.defaults = {
            "defaultModel": "gpt-6.1-sol",
            "defaultThinkingLevel": "high",
            "extensions": ["-builtin:mcp"],
        }
        self.save("settings.json", self.settings)
        self.save("models.json", self.models)
        self.save("auth.json", {"test-provider": {"type": "api_key", "key": "private-example"}})

    def save(self, name, value):
        (self.agent / name).write_text(json.dumps(value))

    def read(self, name):
        return json.loads((self.agent / name).read_text())

    def test_migration_preserves_provider_credentials_limits_and_unrelated_settings(self):
        auth = (self.agent / "auth.json").read_bytes()
        module.initialize(self.agent, self.state, self.defaults)
        settings = self.read("settings.json")
        self.assertEqual(settings["defaultModel"], "gpt-6.1-sol")
        self.assertEqual(settings["defaultThinkingLevel"], "high")
        self.assertEqual(settings["theme"], "custom-theme")
        self.assertEqual(settings["defaultProvider"], "test-provider")
        self.assertEqual(settings["extensions"], ["custom-extension.ts", "-builtin:mcp"])
        provider = self.read("models.json")["providers"]["test-provider"]
        self.assertEqual(provider["baseUrl"], self.models["providers"]["test-provider"]["baseUrl"])
        self.assertEqual(provider["headers"], {"X-Test": "private-example"})
        self.assertEqual(provider["models"][0], self.models["providers"]["test-provider"]["models"][0])
        added = provider["models"][1]
        self.assertEqual(added["contextWindow"], 123456)
        self.assertEqual(added["maxTokens"], 12345)
        self.assertEqual(added["thinkingLevelMap"]["max"], "max")
        self.assertIsNone(added["thinkingLevelMap"]["off"])
        self.assertEqual((self.agent / "auth.json").read_bytes(), auth)
        marker = json.loads((self.state / "initialized-v1.json").read_text())
        backup = Path(marker["backup"])
        self.assertEqual(json.loads((backup / "settings.json").read_text()), self.settings)
        self.assertEqual(json.loads((backup / "models.json").read_text()), self.models)
        self.assertEqual((backup / "models.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)

    def test_later_activation_preserves_changed_defaults_without_duplicate_models(self):
        module.initialize(self.agent, self.state, self.defaults)
        settings = self.read("settings.json")
        settings.update(defaultModel="another-model", defaultThinkingLevel="max")
        self.save("settings.json", settings)
        models = (self.agent / "models.json").read_bytes()
        module.initialize(self.agent, self.state, self.defaults)
        self.assertEqual(self.read("settings.json"), settings)
        self.assertEqual((self.agent / "models.json").read_bytes(), models)

    def test_invalid_custom_provider_fails_before_writing_live_files(self):
        self.models["providers"]["test-provider"]["api"] = "unsupported-api"
        self.save("models.json", self.models)
        before = {path.name: path.read_bytes() for path in self.agent.iterdir()}
        with self.assertRaisesRegex(ValueError, "openai-responses"):
            module.initialize(self.agent, self.state, self.defaults)
        self.assertEqual({path.name: path.read_bytes() for path in self.agent.iterdir()}, before)
        self.assertFalse((self.state / "initialized-v1.json").exists())


if __name__ == "__main__":
    unittest.main()
