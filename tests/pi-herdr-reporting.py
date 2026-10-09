#!/usr/bin/env python3
"""Official Herdr reporter lifecycle against a fake socket; never contacts a live session."""

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_test_support import isolated_environment


class Reporting(unittest.TestCase):
    def test_root_re_question_reload_settlement_and_headless_isolation(self):
        integration = (
            Path(shutil.which("herdr")).resolve().parents[1]
            / "share/herdr/integrations/pi/herdr-agent-state.ts"
        )
        observed = []
        with tempfile.TemporaryDirectory(prefix="pi-herdr-reporting-") as temporary:
            root = Path(temporary)
            endpoint = socket.socket(socket.AF_UNIX)
            endpoint.bind(str(root / "fake.sock"))
            endpoint.listen()
            endpoint.settimeout(0.2)
            stop = threading.Event()

            def serve():
                while not stop.is_set():
                    try:
                        connection, _ = endpoint.accept()
                    except socket.timeout:
                        continue
                    with connection:
                        connection.settimeout(2)
                        data = b""
                        while b"\n" not in data:
                            data += connection.recv(65536)
                        observed.append(json.loads(data))
                        connection.sendall(b'{"result":{}}\n')

            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            try:
                probe = root / "probe.ts"
                probe.write_text(
                    """
import reporter from INTEGRATION;
import {EventEmitter} from "node:events";
const handlers = new Map();
const events = new EventEmitter();
reporter({events, on: (name, handler) => handlers.set(name, handler)});
let idle = false;
const ctx = {mode: "json", isIdle: () => idle, sessionManager: {
 getSessionFile: () => process.env.RE_SESSION, getSessionId: () => "re-root"}};
const wait = () => new Promise(resolve => setTimeout(resolve, 50));
for (const mode of ["print", "json", "rpc"]) {
 ctx.mode = mode;
 await handlers.get("session_start")({reason: "resume"}, ctx);
 handlers.get("agent_start")({}, ctx);
 events.emit("herdr:blocked", {active: true, label: "must not report"});
 await wait();
}
await Bun.write(process.env.HEADLESS_MARKER, "done");
ctx.mode = "tui";
await handlers.get("session_start")({reason: "resume"}, ctx); // reload mid-run
await wait();
events.emit("herdr:blocked", {active: true, label: "Authorize fixture?"});
await wait();
events.emit("herdr:blocked", {active: false});
await wait();
idle = true;
handlers.get("agent_settled")({}, ctx);
await wait();
handlers.get("agent_start")({}, ctx);
await wait();
""".replace("INTEGRATION", json.dumps(str(integration)))
                )
                env = isolated_environment()
                env.update(
                    HERDR_ENV="1",
                    HERDR_SOCKET_PATH=str(root / "fake.sock"),
                    HERDR_PANE_ID="wA:pB",
                    RE_SESSION=str(root / "pi-re/sessions/root.jsonl"),
                    HEADLESS_MARKER=str(root / "headless"),
                )
                process = subprocess.run(
                    [shutil.which("bun"), str(probe)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                states = [
                    request["params"]
                    for request in observed
                    if request["method"] == "pane.report_agent"
                ]
                self.assertEqual(
                    [state["state"] for state in states],
                    ["working", "blocked", "working", "idle", "working"],
                )
                self.assertEqual(states[1]["message"], "Authorize fixture?")
                for request in observed:
                    self.assertEqual(request["params"]["pane_id"], "wA:pB")
                    self.assertEqual(request["params"]["agent_session_path"], env["RE_SESSION"])
                    self.assertEqual(request["params"]["agent"], "pi")
                sessions = [r for r in observed if r["method"] == "pane.report_agent_session"]
                self.assertEqual(len(sessions), 2)  # headless start emitted none
                self.assertEqual(sessions[0]["params"]["session_start_source"], "resume")
            finally:
                stop.set()
                thread.join(timeout=3)
                endpoint.close()


if __name__ == "__main__":
    unittest.main()
