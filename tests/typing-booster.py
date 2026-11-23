#!/usr/bin/env python3
"""Exercise the typing-mode toggle with an isolated, mocked IBus daemon."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOGGLE = ROOT / "home-manager/modules/desktop/typing-booster-toggle.sh"


class TypingBoosterToggle(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="typing-booster-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.engine = self.root / "engine"
        self.previous = self.root / "typing-booster-previous-engine"
        mock = self.root / "ibus"
        mock.write_text("""#!/usr/bin/env bash
set -eu
[[ "$1" == engine ]]
if [[ "$#" == 1 ]]; then
  [[ "${FAIL_QUERY:-0}" == 0 ]] || exit 1
  read -r current < "$XDG_RUNTIME_DIR/engine"
  printf '%s\\n' "$current"
else
  [[ "${FAIL_SWITCH:-0}" == 0 ]] || exit 1
  printf '%s\\n' "$2" > "$XDG_RUNTIME_DIR/engine"
  if [[ "$2" != typing-booster && -n "${PAUSE_NOTIFY_FD:-}" ]]; then
    printf 'ready\\n' >&"$PAUSE_NOTIFY_FD"
    read -r _ <&"$PAUSE_RELEASE_FD"
  fi
fi
""")
        mock.chmod(0o755)
        self.env = dict(
            os.environ,
            XDG_RUNTIME_DIR=str(self.root),
            PATH=f"{self.root}:{os.environ['PATH']}",
        )

    def toggle(self, **environment):
        return subprocess.run(
            ["bash", "-euo", "pipefail", str(TOGGLE)],
            env=dict(self.env, **environment),
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_restores_the_actual_previous_engine(self):
        for engine in ["xkb:us::eng", "xkb:ara::ara", "another-engine"]:
            with self.subTest(engine=engine):
                self.engine.write_text(engine + "\n")
                result = self.toggle()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.engine.read_text(), "typing-booster\n")
                self.assertEqual(self.previous.read_text(), engine + "\n")
                result = self.toggle()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.engine.read_text(), engine + "\n")
                self.assertFalse(self.previous.exists())

    def test_overlapping_presses_preserve_the_saved_engine(self):
        self.engine.write_text("typing-booster\n")
        self.previous.write_text("previous-engine\n")
        notify_read, notify_write = os.pipe()
        release_read, release_write = os.pipe()
        with os.fdopen(notify_read) as notify, os.fdopen(release_write, "w") as release:
            with subprocess.Popen(
                ["bash", "-euo", "pipefail", str(TOGGLE)],
                env=dict(
                    self.env,
                    PAUSE_NOTIFY_FD=str(notify_write),
                    PAUSE_RELEASE_FD=str(release_read),
                ),
                pass_fds=(notify_write, release_read),
            ) as first:
                os.close(notify_write)
                os.close(release_read)
                try:
                    self.assertEqual(notify.readline(), "ready\n")
                    with subprocess.Popen(
                        ["bash", "-euo", "pipefail", str(TOGGLE)], env=self.env
                    ) as second:
                        try:
                            # A second press must wait for the entire first transaction.
                            with self.assertRaises(subprocess.TimeoutExpired):
                                second.wait(timeout=0.2)
                        finally:
                            release.write("continue\n")
                            release.flush()
                            self.assertEqual(first.wait(timeout=5), 0)
                            self.assertEqual(second.wait(timeout=5), 0)
                finally:
                    if first.poll() is None:
                        first.kill()
        self.assertEqual(self.engine.read_text(), "typing-booster\n")
        self.assertEqual(self.previous.read_text(), "previous-engine\n")
        self.assertEqual(self.toggle().returncode, 0)
        self.assertEqual(self.engine.read_text(), "previous-engine\n")

    def test_missing_previous_engine_is_not_guessed(self):
        self.engine.write_text("typing-booster\n")
        result = self.toggle()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Previous input engine unknown", result.stderr)
        self.assertEqual(self.engine.read_text(), "typing-booster\n")

    def test_failed_query_leaves_saved_engine_untouched(self):
        self.engine.write_text("typing-booster\n")
        self.previous.write_text("previous-engine\n")
        result = self.toggle(FAIL_QUERY="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.previous.read_text(), "previous-engine\n")

    def test_failed_restore_keeps_saved_engine_for_retry(self):
        self.engine.write_text("typing-booster\n")
        self.previous.write_text("previous-engine\n")
        result = self.toggle(FAIL_SWITCH="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.engine.read_text(), "typing-booster\n")
        self.assertEqual(self.previous.read_text(), "previous-engine\n")

    def test_failed_enable_keeps_original_engine(self):
        self.engine.write_text("previous-engine\n")
        result = self.toggle(FAIL_SWITCH="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.engine.read_text(), "previous-engine\n")


class TypingBoosterEngine(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("TYPING_BOOSTER_ENGINE"), "package check is opt-in")
    def test_packaged_dictionary_and_spelling_backend(self):
        with tempfile.TemporaryDirectory(prefix="typing-engine-test-") as temporary:
            root = Path(temporary)
            # Run inside the real wrapper environment, before its harmless --xml action.
            (root / "sitecustomize.py").write_text("""import os
import sys
try:
    sys.path.insert(0, os.environ['IBUS_TYPING_BOOSTER_LOCATION'] + '/engine')
    import hunspell_suggest
    assert hunspell_suggest.IMPORT_ENCHANT_SUCCESSFUL
    dictionary = hunspell_suggest.Hunspell(['en_US'])
    assert 'hello' in dict(dictionary.suggest('hell'))
    assert 'hello' in dict(dictionary.suggest('helo'))
    print('TYPING_BOOSTER_BACKEND_OK')
except BaseException:
    import traceback
    traceback.print_exc()
    os._exit(1)
""")
            result = subprocess.run(
                [
                    str(
                        Path(os.environ["TYPING_BOOSTER_ENGINE"])
                        / "libexec/ibus-engine-typing-booster"
                    ),
                    "--xml",
                ],
                env=dict(
                    os.environ,
                    PYTHONPATH=str(root),
                    XDG_CACHE_HOME=str(root / "cache"),
                    XDG_CONFIG_HOME=str(root / "config"),
                    XDG_DATA_HOME=str(root / "data"),
                ),
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("TYPING_BOOSTER_BACKEND_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
