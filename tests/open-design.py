"""Smoke-test a built OpenDesign package without user data or model requests.

Usage: python3 tests/open-design.py /path/to/package/bin/open-design
"""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    executable = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="open-design-test-") as directory:
        root = Path(directory)
        home = root / "home"
        home.mkdir()
        mock_bin = root / "bin"
        mock_bin.mkdir()
        codex = mock_bin / "codex"
        codex.write_text("#!/bin/sh\nprintf 'codex-cli 0.157.0\\n'\n")
        codex.chmod(0o755)
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("OD_", "OPEN_DESIGN_"))
        }
        environment.update(
            HOME=str(home),
            PATH=str(mock_bin),
            XDG_CONFIG_HOME=str(root / "config"),
            XDG_DATA_HOME=str(root / "data"),
            XDG_CACHE_HOME=str(root / "cache"),
            XDG_STATE_HOME=str(root / "state"),
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        # Ignore caller proxy settings for loopback test requests.
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def get(path):
            with client.open(origin + path, timeout=20) as response:
                return response.read().decode()

        with (root / "daemon.log").open("w+") as log:
            daemon = subprocess.Popen(
                [str(executable), "--no-open", "--port", str(port)],
                cwd=home,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    if daemon.poll() is not None:
                        raise AssertionError("OpenDesign exited before becoming ready")
                    try:
                        assert json.loads(get("/api/health"))["ok"]
                        break
                    except urllib.error.URLError:
                        time.sleep(0.2)
                else:
                    raise AssertionError("OpenDesign startup timed out")

                html = get("/")
                assert "<!DOCTYPE html>" in html
                asset = re.search(r'src="(/_next/static/[^\"]+\.js)"', html)
                assert asset, "Static export must reference a JavaScript bundle"
                assert get(asset.group(1)), "Static JavaScript bundle must be served"
                for endpoint, key in [
                    ("skills", "skills"),
                    ("design-templates", "designTemplates"),
                    ("design-systems", "designSystems"),
                ]:
                    entries = json.loads(get(f"/api/{endpoint}"))[key]
                    assert entries, f"Bundled {endpoint} must be discoverable"
                    print(f"PASS: {len(entries)} bundled {endpoint}")
                agents = json.loads(get("/api/agents"))["agents"]
                detected = next(agent for agent in agents if agent["id"] == "codex")
                assert detected["available"], "Caller PATH agent must be detected"
                assert Path(detected["path"]).resolve() == codex
                assert (root / "data" / "open-design").is_dir()
                assert not (home / ".od").exists(), "No cwd-relative data fallback"
                print("PASS: web assets, health, caller PATH, and XDG data isolation")
            except BaseException:
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                if daemon.poll() is None:
                    os.killpg(daemon.pid, signal.SIGTERM)
                try:
                    daemon.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(daemon.pid, signal.SIGKILL)
                    daemon.wait()


if __name__ == "__main__":
    main()
