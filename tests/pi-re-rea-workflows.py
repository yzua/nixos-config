#!/usr/bin/env python3
"""Opt-in owned REA MCP/network/process/browser checks; no login, device or model."""

import argparse
import hashlib
import http.server
import json
import os
import selectors
import shutil
import signal
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path


def evidence(result):
    if "structuredContent" in result:
        return result["structuredContent"]
    return json.loads(next(item["text"] for item in result["content"] if item["type"] == "text"))


class Mcp:
    def __init__(self, launcher, env, directory):
        self.stderr = (directory / "mcp.stderr").open("w")
        self.process = subprocess.Popen(
            [str(launcher), "rea-mcp"],
            env=env,
            cwd=directory,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            start_new_session=True,
        )
        self.identifier = 0
        self.buffer = b""
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        result = self.request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "owned-rea-fixtures", "version": "1"},
            },
        )
        assert result["serverInfo"]["version"] == "6.5.0"
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def send(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        self.process.stdin.flush()

    def request(self, method, params, timeout=420):
        self.identifier += 1
        identifier = self.identifier
        self.send({"jsonrpc": "2.0", "id": identifier, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                message = json.loads(line)
                if message.get("id") == identifier:
                    assert "error" not in message, message
                    return message["result"]
            remaining = deadline - time.monotonic()
            assert remaining > 0 and self.selector.select(remaining), f"MCP timeout: {method}"
            chunk = os.read(self.process.stdout.fileno(), 65536)
            assert chunk, f"MCP EOF: {method}"
            self.buffer += chunk
            assert len(self.buffer) <= 16 * 1024 * 1024, "MCP fixture output budget"

    def call(self, name, args):
        result = self.request("tools/call", {"name": name, "arguments": args})
        assert not result.get("isError"), result
        return result

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGTERM)
            self.process.wait(timeout=15)
            raise AssertionError("MCP did not exit/clean up after EOF") from None
        finally:
            self.selector.close()
            self.process.stdout.close()
            self.stderr.close()
        assert self.process.returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi-re", type=Path, required=True)
    parser.add_argument("--native", type=Path, help="Optional owned static native fixture")
    parser.add_argument("--browser", type=Path, help="Optional configured Chrome executable")
    parser.add_argument(
        "--python", type=Path, help="Optional pinned Python with mitmproxy to create native flows"
    )
    args = parser.parse_args()
    launcher = args.pi_re.resolve(strict=True)
    checks = []
    with tempfile.TemporaryDirectory(prefix="pi-re-rea-workflows-") as temporary:
        directory = Path(temporary)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("PI_", "XDG_", "REA_", "HOPPER_", "HERDR_"))
            and not key.endswith(("_API_KEY", "_TOKEN"))
            and key
            not in {
                "NODE_OPTIONS",
                "NODE_PATH",
                "JAVA_TOOL_OPTIONS",
                "_JAVA_OPTIONS",
                "JDK_JAVA_OPTIONS",
            }
        }
        env.update(
            HOME=temporary,
            XDG_STATE_HOME=str(directory / "state"),
            XDG_DATA_HOME=str(directory / "data"),
        )
        har = directory / "owned.har"
        har.write_text(
            json.dumps(
                {
                    "log": {
                        "version": "1.2",
                        "creator": {"name": "owned-fixture", "version": "1"},
                        "entries": [
                            {
                                "startedDateTime": "2026-01-01T00:00:00.000Z",
                                "time": 1,
                                "request": {
                                    "method": "GET",
                                    "url": "https://fixture.invalid/owned",
                                    "httpVersion": "HTTP/1.1",
                                    "cookies": [],
                                    "headers": [],
                                    "queryString": [],
                                    "headersSize": -1,
                                    "bodySize": 0,
                                },
                                "response": {
                                    "status": 200,
                                    "statusText": "OK",
                                    "httpVersion": "HTTP/1.1",
                                    "cookies": [],
                                    "headers": [],
                                    "content": {
                                        "size": 18,
                                        "mimeType": "text/plain",
                                        "text": "REA_NETWORK_MARKER",
                                    },
                                    "redirectURL": "",
                                    "headersSize": -1,
                                    "bodySize": 18,
                                },
                                "cache": {},
                                "timings": {"send": 0, "wait": 1, "receive": 0},
                            }
                        ],
                    }
                }
            )
        )
        before = hashlib.sha256(har.read_bytes()).hexdigest()
        cli = subprocess.run(
            [str(launcher), "rea", "inspect-web-network-capture", str(har), "har", "--json"],
            env=env,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert cli.returncode == 0, cli.stderr + cli.stdout
        assert json.loads(cli.stdout)["operation"] == "inspect_web_network_capture"
        assert "REA_NETWORK_MARKER" in cli.stdout
        checks.append("cli-offline-har")
        client = Mcp(launcher, env, directory)
        try:
            tools = client.request("tools/list", {})["tools"]
            assert len(tools) == 207
            inventory = {tool["name"] for tool in tools}
            assert {
                "open_binary",
                "close_binary",
                "get_call_graph",
                "set_address_name",
                "inspect_web_network_capture",
                "capture_browser_scenario",
                "inspect_sqlite_database",
                "inspect_packet_capture",
                "inspect_go_binary",
                "inspect_rust_binary",
                "identify_flutter_build",
                "inspect_dart_aot",
                "inspect_electron_fuses",
            } <= inventory
            checks.append("mcp-207-tools")
            result = client.call(
                "inspect_web_network_capture", {"capture_path": str(har), "format": "har"}
            )
            assert "REA_NETWORK_MARKER" in json.dumps(result)
            checks.append("mcp-offline-har")
            summary = evidence(
                client.call(
                    "inspect_web_network_capture",
                    {"capture_path": str(har), "format": "har", "detail": "summary"},
                )
            )
            parent = summary["normalized_result"]["parent_evidence_id"]
            page = evidence(
                client.call(
                    "inspect_analysis_view",
                    {
                        "source": {"kind": "retained-evidence", "evidence_id": parent},
                        "view": {"kind": "capture", "detail": "complete", "offset": 0, "limit": 1},
                    },
                )
            )
            assert page["normalized_result"]["parent_evidence_id"] == parent
            assert "REA_NETWORK_MARKER" in json.dumps(page)
            assert len(json.dumps(page)) <= 128 * 1024
            checks.append("mcp-retained-capture-summary-page")
            malformed = directory / "malformed.sqlite"
            malformed.write_bytes(b"owned malformed SQLite fixture")
            result = client.request(
                "tools/call",
                {"name": "inspect_sqlite_database", "arguments": {"path": str(malformed)}},
            )
            assert result.get("isError"), result
            checks.append("mcp-malformed-sqlite")
            # One synthetic Ethernet/IPv4/UDP packet; never acquire live traffic.
            packet = (
                bytes.fromhex("0000000000010000000000020800")
                + bytes.fromhex("450000200001000040117cc67f0000017f000002")
                + struct.pack("!HHHH", 12345, 54321, 12, 0)
                + b"REA!"
            )
            pcap = directory / "owned.pcap"
            pcap.write_bytes(
                struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
                + struct.pack("<IIII", 1, 0, len(packet), len(packet))
                + packet
            )
            packet_hash = hashlib.sha256(pcap.read_bytes()).hexdigest()
            result = client.call(
                "inspect_packet_capture",
                {"path": str(pcap), "fields": ["ip.src", "udp.dstport"], "match_limit": 1},
            )
            assert "54321" in json.dumps(result), result
            client.call("inspect_pcap_client", {})
            result = client.call("inspect_pcap_capture", {"path": str(pcap)})
            assert "127.0.0.1" in json.dumps(result), result
            assert hashlib.sha256(pcap.read_bytes()).hexdigest() == packet_hash
            checks.append("mcp-offline-packet-and-pcap")
            malformed = directory / "malformed.pcap"
            malformed.write_bytes(b"owned malformed packet fixture")
            result = client.request(
                "tools/call",
                {
                    "name": "inspect_packet_capture",
                    "arguments": {"path": str(malformed), "fields": ["ip.src"]},
                },
            )
            assert result.get("isError"), result
            failure = evidence(result)["error"]
            assert failure["code"] == "execution_failure", failure
            assert failure["details"]["provider_id"] == "tshark-capture", failure
            assert "isn't a capture file" in failure["details"]["diagnostics"]["stderr"], failure
            checks.append("mcp-malformed-packet")
            if args.python:
                flow = directory / "owned.mitm"
                source = (
                    "from mitmproxy import http,io,connection;import sys;"
                    "c=connection.Client(peername=('127.0.0.1',1234),sockname=('127.0.0.1',8080));"
                    "s=connection.Server(address=('fixture.invalid',443));f=http.HTTPFlow(c,s);"
                    "f.request=http.Request.make('GET','https://fixture.invalid/native');"
                    "f.response=http.Response.make(200,b'REA_NATIVE_FLOW_MARKER');"
                    "s=open(sys.argv[1],'wb');io.FlowWriter(s).add(f);s.close()"
                )
                subprocess.run(
                    [str(args.python.resolve(strict=True)), "-c", source, str(flow)],
                    env=env,
                    check=True,
                    timeout=30,
                )
                result = client.call(
                    "inspect_web_network_capture",
                    {"capture_path": str(flow), "format": "mitmproxy"},
                )
                assert "REA_NATIVE_FLOW_MARKER" in json.dumps(result)
                checks.append("mcp-native-mitmproxy")
            result = client.call(
                "capture_process_scenario",
                {
                    "executable": shutil.which("printf"),
                    "arguments": ["REA_PROCESS_MARKER\\n"],
                    "working_directory": temporary,
                    "timeout_ms": 5000,
                    "idle_timeout_ms": 5000,
                },
            )
            assert "REA_PROCESS_MARKER" in json.dumps(result)
            checks.append("owned-process-pty")
            if args.native:
                native = args.native.resolve(strict=True)
                digest = hashlib.sha256(native.read_bytes()).hexdigest()
                client.call("open_binary", {"path": str(native), "provider_id": "ghidra"})
                result = client.call("analyze_function", {"procedure": "rea_leaf"})
                assert "PI_RE_REA_SENTINEL" in json.dumps(result)
                graph = evidence(client.call("get_call_graph", {"address": "rea_leaf"}))[
                    "normalized_result"
                ]
                assert "graph" in graph and "limitations" in graph
                client.call("close_binary", {})
                assert hashlib.sha256(native.read_bytes()).hexdigest() == digest
                checks.append("mcp-persistent-ghidra-function-close")
            if args.browser:

                class Handler(http.server.BaseHTTPRequestHandler):
                    def log_message(self, *_args):
                        pass

                    def do_GET(self):
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(
                            b"<!doctype html><title>REA_BROWSER_MARKER</title><button onclick=\"this.textContent='REA_CLICK_MARKER'\">Owned</button>"
                        )

                server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    result = client.call(
                        "capture_browser_scenario",
                        {
                            "browser": {
                                "mode": "launch",
                                "executable_path": str(args.browser.resolve(strict=True)),
                                "headless": True,
                            },
                            "start_url": {"url": f"http://127.0.0.1:{server.server_port}/"},
                            "actions": [
                                {
                                    "step_id": "click",
                                    "action": "click",
                                    "locator": {"kind": "role", "role": "button", "name": "Owned"},
                                    "timeout_ms": 10000,
                                }
                            ],
                            "capture": {"at_end": ["dom", "url"], "events": ["network"]},
                        },
                    )
                    assert "REA_CLICK_MARKER" in json.dumps(result)
                    checks.append("owned-browser-click-network-cleanup")
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
        finally:
            client.close()
        assert hashlib.sha256(har.read_bytes()).hexdigest() == before
        assert not (directory / "data/pi-re/agent").exists(), "MCP transport touched coding login"
        print(
            json.dumps(
                {
                    "status": "passed",
                    "checks": checks,
                    "limits": "owned fixtures only; no device, external site, model or optional engine qualification",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
