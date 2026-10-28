#!/usr/bin/env python3
"""Pi loader isolation with loopback sources and synthetic credentials.

--pi uses checkout resources plus managed dependencies (PI_WEB_FETCH_DIR).
--pi-re reads public resource routing from the selected managed launcher itself;
no coding-profile dependency installation or search configuration is needed.
"""

import argparse
import http.server
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from pi_test_support import pdf_fixture, require_web_fetch_dependencies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    launch = parser.add_mutually_exclusive_group(required=True)
    launch.add_argument("--pi", type=Path, help="Test checkout resources with this Pi executable")
    launch.add_argument("--pi-re", type=Path, help="Test this installed global pi-re launcher")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    code = root / "home-manager/modules/ai/pi-re"
    release = json.loads((root / "tests/fixtures/pi-re-rea/release-inventory.json").read_text())
    if args.pi_re:
        # Read only the selected managed launcher's public immutable configuration.
        # Built-mode fixtures need no coding-profile resources or dependencies.
        assignment = next(
            line
            for line in args.pi_re.resolve().read_text().splitlines()
            if line.startswith("export PI_RE_CONFIG=")
        )
        runtime_path = Path(shlex.split(assignment)[1].removeprefix("PI_RE_CONFIG="))
        runtime_config = json.loads(runtime_path.read_text())
        search_config = Path(runtime_config["webSearchExtension"]).with_name("config.json")
        search_backend = json.loads(search_config.read_text())
    else:
        fetch_dependencies = require_web_fetch_dependencies().resolve() / "node_modules"
        search_backend = {"provider": "fixture-search", "model": "fixture-search-model"}
    observed = []
    search_requests = []
    fetch_requests = []
    research_requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            fetch_requests.append((self.path, self.headers.get("Authorization")))
            article = (
                "<html><head><title>RE public manual fixture</title></head>"
                "<body><article><h1>PI-RE-HTML-MARKER</h1>"
                + "<p>Public synthetic documentation for the loader fixture.</p>" * 30
                + "</article></body></html>"
            ).encode()
            content_type, body = {
                "/article": ("text/html", article),
                "/sample.pdf": ("application/pdf", pdf_fixture()),
                "/manual.txt": ("text/plain", b"PI_RE_TEXT_MARKER: synthetic manual"),
            }[self.path]
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers["Content-Length"])
            assert length < 1024 * 1024
            body = json.loads(self.rfile.read(length))
            if self.path == "/backend-api/codex/alpha/search":
                search_requests.append((body, self.headers.get("Authorization")))
                response = json.dumps(
                    {
                        "output": "PI_RE_SEARCH_MARKER",
                        "results": [
                            {
                                "type": "text_result",
                                "title": "PI_RE_SEARCH_MARKER",
                                "url": f"http://127.0.0.1:{self.server.server_port}/article",
                                "snippet": "Synthetic public documentation",
                            }
                        ],
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                return
            is_research = body.get("model") == "glm-5.3-flash"
            (research_requests if is_research else observed).append(body)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if is_research:
                names = {tool["function"]["name"] for tool in body.get("tools", [])}
                assert names == {"research_read", "research_list", "web_search", "web_fetch"}
                answer = (
                    "RESEARCH_RESUME_OK"
                    if "RESEARCH_FOLLOWUP_MARKER" in json.dumps(body)
                    else "RESEARCH_FIRST_OK"
                )
                deltas = (({"role": "assistant", "content": answer}, None), ({}, "stop"))
            elif args.pi_re and len(observed) == 1:
                # Exercise the actual Pi Bash tool with no ambient shell or launcher.
                # A mock model requests a harmless pinned-CLI version check.
                command = (
                    "for tool in sh bash file readelf grep sed rg jq sha256sum; do "
                    'command -v "$tool" >/dev/null || exit 1; done; pi-re rea --version'
                )
                deltas = (
                    (
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "fixture_rea_version",
                                    "type": "function",
                                    "function": {
                                        "name": "bash",
                                        "arguments": json.dumps(
                                            {"command": command, "timeout": 30}
                                        ),
                                    },
                                }
                            ],
                        },
                        None,
                    ),
                    ({}, "tool_calls"),
                )
            elif args.pi_re and len(observed) == 2:
                # Exercise native Pi codemode discovery and a real MCP call without a model.
                tool = next(
                    tool["function"]
                    for tool in observed[-1]["tools"]
                    if tool["function"]["name"] == "codemode"
                )
                properties = tool["parameters"]["properties"]
                field = next(iter(properties))
                script = (
                    'const ns = await describeNamespace("mcp__rea");'
                    f"if (!ns || ns.tools.length !== {release['mcp_count']}) "
                    'throw new Error("REA tool inventory missing");'
                    "const r = await tools.mcp__rea__binary_session({});"
                    "if (r.isError) throw new Error(JSON.stringify(r));"
                    'text("REA_MCP_DISCOVERY_OK");'
                )
                deltas = (
                    (
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "fixture_rea_mcp",
                                    "type": "function",
                                    "function": {
                                        "name": "codemode",
                                        "arguments": json.dumps({field: script}),
                                    },
                                }
                            ],
                        },
                        None,
                    ),
                    ({}, "tool_calls"),
                )
            elif len(observed) == (3 if args.pi_re else 1):
                base = f"http://127.0.0.1:{self.server.server_port}"
                calls = [
                    ("web_fetch", {"url": base + path})
                    for path in ("/article", "/sample.pdf", "/manual.txt")
                ] + [("web_search", {"query": "synthetic public manual", "limit": 1})]
                deltas = (
                    (
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "index": index,
                                    "id": f"fixture_web_{index}",
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(params)},
                                }
                                for index, (name, params) in enumerate(calls)
                            ],
                        },
                        None,
                    ),
                    ({}, "tool_calls"),
                )
            elif len(observed) in ((4, 5) if args.pi_re else (2, 3)):
                resume = len(observed) == (5 if args.pi_re else 3)
                name = "research_subagent_message" if resume else "research_subagent"
                params = (
                    {
                        "name": "docs-fixture",
                        "message": "RESEARCH_FOLLOWUP_MARKER",
                        "timeout_seconds": 30,
                    }
                    if resume
                    else {
                        "name": "docs-fixture",
                        "task": "ROOT_RESEARCH_FIRST_MARKER",
                        "cwd": str(project),
                        "timeout_seconds": 30,
                    }
                )
                deltas = (
                    (
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "fixture_research_" + str(resume),
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(params)},
                                }
                            ],
                        },
                        None,
                    ),
                    ({}, "tool_calls"),
                )
            else:
                deltas = (
                    ({"role": "assistant", "content": "LOADER_FIXTURE_OK"}, None),
                    ({}, "stop"),
                )
            for delta, finish in deltas:
                chunk = {
                    "id": "fixture",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "fixture",
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                }
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    with tempfile.TemporaryDirectory(prefix="pi-re-loader-") as temporary:
        home = Path(temporary)
        project = home / "hostile-project"
        project.mkdir()
        (project / "AGENTS.md").write_text("UNTRUSTED_CONTEXT_CANARY_DO_NOT_LOAD")
        extension = project / ".pi/extensions"
        extension.mkdir(parents=True)
        marker = home / "extension-ran"
        (extension / "unsafe.ts").write_text(
            f'import fs from "node:fs"; export default function() {{ fs.writeFileSync({json.dumps(str(marker))}, "unsafe"); }}'
        )
        skill = project / ".pi/skills/unreviewed"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: UNREVIEWED_SKILL_CANARY\ndescription: Never load this.\n---\nUnsafe fixture"
        )
        common_chrome = home / "pinned-skills/chrome-devtools-cli"
        common_chrome.mkdir(parents=True)
        (common_chrome / "SKILL.md").write_text(
            "---\nname: chrome-devtools-cli\ndescription: Shared browser CLI guidance.\n---\nNo browser startup during discovery.\n"
        )
        source = home / ".pi/agent"
        source.mkdir(parents=True)
        mcp_marker = home / "unreviewed-mcp-ran"
        poison_mcp = json.dumps(
            {
                "mcpServers": {
                    name: {
                        "command": os.sys.executable,
                        "args": ["-c", f"open({str(mcp_marker)!r}, 'w').write('bad')"],
                    }
                    for name in ("rea", "foreign")
                }
            }
        )
        for mcp_path in (source / "mcp.json", project / ".pi/mcp.json"):
            mcp_path.write_text(poison_mcp)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            model = {
                "id": "fixture",
                "name": "fixture",
                "reasoning": False,
                "input": ["text"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": 128000,
                "maxTokens": 1024,
            }
            models = {
                "providers": {
                    "fixture": {
                        "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                        "api": "openai-completions",
                        "apiKey": "FIXTURE_PRIVATE_KEY_CANARY",
                        "models": [model],
                    }
                }
            }
            models["providers"][search_backend["provider"]] = {
                "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                "api": "openai-responses",
                "apiKey": "FIXTURE_RE_SEARCH_KEY_CANARY",
                "models": [{**model, "id": search_backend["model"]}],
            }
            models["providers"]["zai"] = {
                "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                "api": "openai-completions",
                "apiKey": "FIXTURE_RESEARCH_KEY_CANARY",
                "models": [{**model, "id": "glm-5.3-flash"}],
            }
            data = home / "isolated-data"
            state = home / "isolated-state"
            agent = source
            re_state = state / "pi-re"
            destination = source
            for directory in (agent, re_state):
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            for name, value in {
                "settings.json": {
                    "defaultProvider": "fixture",
                    "defaultModel": "fixture",
                    "defaultProjectTrust": "always",
                    "extensions": ["+builtin:mcp", str(extension / "unsafe.ts")],
                    "skills": [str(skill)],
                    "sessionDir": str(home / "forbidden-shared-sessions"),
                    "defaultTools": ["read"],
                    "enableInstallTelemetry": False,
                    "enableAnalytics": False,
                },
                "models.json": models,
                "auth.json": {},
            }.items():
                path = destination / name
                path.write_text(json.dumps(value))
                path.chmod(0o600)
            env = os.environ.copy()
            for key in list(env):
                if (
                    key.startswith(("PI_", "XDG_"))
                    or key.endswith(("_API_KEY", "_TOKEN"))
                    or key in ("IN_NIX_SHELL", "NIX_BUILD_TOP")
                ):
                    del env[key]
            env.update(HOME=str(home), XDG_DATA_HOME=str(data), XDG_STATE_HOME=str(state))
            if args.pi_re:
                env["PATH"] = "/nonexistent-ambient-path"
                command = [str(args.pi_re.absolute())]
                doctor = subprocess.run(
                    [*command, "doctor", "--json"],
                    cwd=project,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                assert doctor.returncode == 0, doctor.stderr[-2000:]
                available = {
                    item["id"]
                    for item in json.loads(doctor.stdout)["capabilities"]
                    if item["enabled"]
                }
                assert {
                    "android-static",
                    "android-lab",
                    "agent-device",
                    "traffic",
                    "frida",
                    "rea",
                    "native",
                } <= available
            else:
                # Load current checkout code with managed dependencies and explicit routing.
                search = home / "web-search"
                search.mkdir()
                shutil.copyfile(
                    root / "home-manager/modules/ai/pi-base/extensions/web-search/index.ts",
                    search / "index.ts",
                )
                (search / "config.json").write_text(json.dumps(search_backend))
                fetch = home / "web-fetch"
                fetch.mkdir()
                shutil.copyfile(
                    root / "home-manager/modules/ai/pi-base/extensions/web-fetch/index.ts",
                    fetch / "index.ts",
                )
                (fetch / "node_modules").symlink_to(fetch_dependencies)
                runtime = home / "config.json"
                runtime.write_text(
                    json.dumps(
                        {
                            "pi": str(args.pi.resolve()),
                            "python": os.sys.executable,
                            "resources": str(code),
                            "agentDir": str(source),
                            "commonSkills": [str(common_chrome)],
                            "commonExtensions": [
                                str(
                                    Path(shutil.which("herdr")).resolve().parents[1]
                                    / "share/herdr/integrations/pi/herdr-agent-state.ts"
                                ),
                                str(
                                    root
                                    / "home-manager/modules/ai/pi-base/extensions/ask-user-question.ts"
                                ),
                                str(
                                    root
                                    / "home-manager/modules/ai/pi-base/extensions/upstream-retry.ts"
                                ),
                                str(
                                    root
                                    / "home-manager/modules/ai/pi-base/extensions/network-diagnostics.ts"
                                ),
                                str(
                                    root
                                    / "home-manager/modules/ai/pi-base/extensions/prompt-snippets/index.ts"
                                ),
                                str(
                                    root
                                    / "home-manager/modules/ai/pi-base/extensions/interactive-subagents/pi-extension/subagents/index.ts"
                                ),
                                str(search / "index.ts"),
                                str(fetch / "index.ts"),
                            ],
                            "webSearchExtension": str(search / "index.ts"),
                            "webFetchExtension": str(fetch / "index.ts"),
                            "capabilities": [],
                        }
                    )
                )
                env["PI_RE_CONFIG"] = str(runtime)
                command = [os.sys.executable, "-B", str(code / "launcher.py")]
            result = subprocess.run(
                [
                    *command,
                    "--provider",
                    "fixture",
                    "--model",
                    "fixture",
                    "--thinking",
                    "off",
                    "--print",
                    "--mode",
                    "json",
                    "Check synthetic loopback web sources and pinned REA only. "
                    "PRIVATE_HISTORY_CANARY_DO_NOT_SEARCH",
                ],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            assert result.returncode == 0, result.stderr[-2000:]
            assert "LOADER_FIXTURE_OK" in result.stdout, result.stdout[-2000:]
            assert observed, "Mock provider was not contacted"
            body = json.dumps(observed)
            assert "UNTRUSTED_CONTEXT_CANARY" not in body
            assert "UNREVIEWED_SKILL_CANARY" not in body
            for secret in (
                "FIXTURE_PRIVATE_KEY_CANARY",
                "FIXTURE_RE_SEARCH_KEY_CANARY",
                "FIXTURE_RESEARCH_KEY_CANARY",
            ):
                assert secret not in body + result.stdout + result.stderr
            assert "host" in body and "sandbox" in body
            for name in (
                "re-intake",
                "android-static",
                "android-runtime",
                "web-protocol",
                "native-analysis",
                "finding-validation",
                "adapter-build",
                "re-browser",
                "re-device",
                "rea-analysis",
            ):
                assert name in body, f"Reviewed skill missing: {name}"
            for request in observed:
                assert (
                    json.dumps(request["messages"]).count("<name>chrome-devtools-cli</name>") == 1
                ), "Shared browser skill missing or duplicated within a model request"
            tool_names = {
                tool["function"]["name"]
                for request in observed
                for tool in request.get("tools", [])
            }
            assert {
                "read",
                "bash",
                "edit",
                "write",
                "re_subagent",
                "research_subagent",
                "research_subagent_message",
                "ask_user_question",
                "web_search",
                "web_fetch",
            } <= tool_names, tool_names
            assert {"subagent", "subagent_message", "subagents_list"} <= tool_names, tool_names
            assert "ask_question" not in tool_names, tool_names
            tool_responses = [
                message
                for request in observed
                for message in request.get("messages", [])
                if message.get("role") == "tool"
            ]
            for marker_text in (
                "PI-RE-HTML-MARKER",
                "PI_PDF_MARKER",
                "PI_RE_TEXT_MARKER",
                "PI_RE_SEARCH_MARKER",
                "RESEARCH_FIRST_OK",
                "RESEARCH_RESUME_OK",
            ):
                assert marker_text in json.dumps(tool_responses), tool_responses
            assert sorted(fetch_requests) == [
                ("/article", None),
                ("/manual.txt", None),
                ("/sample.pdf", None),
            ], fetch_requests
            assert len(search_requests) == 1, search_requests
            search_body, authorization = search_requests[0]
            assert authorization == "Bearer FIXTURE_RE_SEARCH_KEY_CANARY"
            assert search_body["model"] == search_backend["model"]
            assert search_body["commands"]["search_query"] == [{"q": "synthetic public manual"}]
            assert "PRIVATE_HISTORY_CANARY" not in json.dumps(search_body)
            assert len(research_requests) == 2, research_requests
            assert "RESEARCH_FIRST_OK" in json.dumps(research_requests[1])
            assert "ROOT_RESEARCH_FIRST_MARKER" in json.dumps(research_requests[1])
            assert "PRIVATE_HISTORY_CANARY" not in json.dumps(research_requests)
            if args.pi_re:
                assert tool_responses and release["version"] in json.dumps(tool_responses), (
                    tool_responses
                )
                assert "reverse-engineer-anything" in body, "Official release skill missing"
                assert "codemode" in tool_names, "MCP discovery tool missing"
                assert "mcp__rea" in body, "Managed REA namespace missing"
                assert "REA_MCP_DISCOVERY_OK" in json.dumps(tool_responses), (
                    "Native MCP call failed"
                )
                assert (agent / "mcp.json").read_text() == poison_mcp, (
                    "Shared MCP config was changed"
                )
                assert (project / ".pi/mcp.json").read_text() == poison_mcp, (
                    "Project MCP config was changed"
                )
                assert not (agent / "mcp-auth.json").exists(), "RE touched shared MCP OAuth storage"
                assert "Executable not found" not in json.dumps(tool_responses)
            assert not marker.exists(), "Hostile project extension was loaded"
            assert not mcp_marker.exists(), "Shared/project MCP registration was connected"
            assert not (home / "forbidden-shared-sessions").exists(), (
                "Shared settings redirected RE history"
            )
            # Initialization diagnostics belong on stderr, preserving JSON mode stdout.
            for line in result.stdout.splitlines():
                json.loads(line)
            sessions = list((re_state / "sessions").glob("*.jsonl"))
            assert sessions, "No separate native session was written"
            print(
                f"{'Global pi-re' if args.pi_re else 'Installed Pi'} loader: reviewed skills, "
                "contract/tools, web research and named worker resume with RE credentials, "
                "hostile cwd excluded, isolated JSON/session state"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    main()
