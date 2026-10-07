#!/usr/bin/env python3
"""Opt-in real REA static fixture checks; never execute targets, boot a device or call models."""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi-re", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True, help="Built owned rea-fixture ELF")
    parser.add_argument("--apk", type=Path, help="Optional locally built owned Android fixture")
    args = parser.parse_args()
    launcher = args.pi_re.resolve(strict=True)
    native = args.native.resolve(strict=True)
    apk = args.apk.resolve(strict=True) if args.apk else None
    hashes = {path: digest(path) for path in (native, apk) if path}
    runtime_before = set(Path("/tmp").glob("rea-ghidra-*"))
    checks = []
    with tempfile.TemporaryDirectory(prefix="pi-re-rea-integration-") as temporary:
        home = Path(temporary)
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
            HOME=str(home), XDG_STATE_HOME=str(home / "state"), XDG_DATA_HOME=str(home / "data")
        )
        # A hostile cwd must not contribute executable resources or instructions.
        cwd = home / "unrelated"
        cwd.mkdir()
        (cwd / "AGENTS.md").write_text("UNTRUSTED_FIXTURE_CONTEXT")

        def run(name, argv, expected=0, structured=True):
            stdout, stderr = home / f"{name}.json", home / f"{name}.stderr"
            with stdout.open("w") as out, stderr.open("w") as err:
                process = subprocess.Popen(
                    [str(launcher), *map(str, argv)],
                    cwd=cwd,
                    env=env,
                    stdout=out,
                    stderr=err,
                    start_new_session=True,
                )
                try:
                    status = process.wait(timeout=420)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired as failure:
                        raise AssertionError(
                            "REA cleanup did not finish after SIGINT; inspect owned processes"
                        ) from failure
                    raise AssertionError(f"REA fixture query timed out: {name}") from None
            assert status == expected, (
                f"{name}: exit {status}; {stderr.read_text()[-3000:]} {stdout.read_text()[-3000:]}"
            )
            assert stdout.stat().st_size <= 8 * 1024 * 1024, f"{name}: output budget exceeded"
            value = json.loads(stdout.read_text()) if structured else stdout.read_text().strip()
            checks.append(name)
            return value

        doctor = run("catalog", ["doctor", "--json"])
        available = {item["id"] for item in doctor["capabilities"] if item["enabled"]}
        assert {"rea", "native", "android-static"} <= available
        assert not doctor["profileInitialized"], (
            "Static queries must not initialize/read coding login"
        )
        assert run("version", ["rea", "--version"], structured=False) == "4.1.0"
        health = run("ghidra-readiness", ["rea", "doctor", "--provider", "ghidra", "--json"])
        assert health["healthy"] and health["scope"]["mode"] == "explicit"
        # NixOS is outside upstream's whole-host distribution allowlist; scoped checks matter.
        native_options = ["--provider", "ghidra", "--json"]
        function = run("native-function", ["rea", "function", native, "rea_leaf", *native_options])
        assert function["operation"] == "analyze_function"
        assert function["provider"]["id"] == "ghidra"
        assert function["provider"]["version"] == "12.1.4"
        assert function["subject"]["digest"]["sha256"] == hashes[native]
        result = function["normalized_result"]
        assert result["procedure"]["name"] == "rea_leaf"
        assert "PI_RE_REA_SENTINEL" in result["pseudocode"]
        assert result["assembly"] and result["callers"]
        assert (
            function["analysis_profile"]["parameters"]["import_mode"]
            == "ephemeral-source-immutable"
        )
        strings = run(
            "native-strings",
            ["rea", "search", native, "PI_RE_REA_SENTINEL", "--kind", "strings", *native_options],
        )
        matches = strings["normalized_result"]
        assert matches, "Known fixture string was not recovered"
        address = next(item["address"] for item in matches if "PI_RE_REA_SENTINEL" in item["value"])
        refs = run("native-xrefs", ["rea", "xrefs", native, address, *native_options])
        assert refs["normalized_result"], "Known string had no incoming references"
        instructions = run(
            "native-instructions", ["rea", "instructions", native, "rea_leaf", *native_options]
        )
        assert instructions["normalized_result"]["instructions"]
        decompiled = run(
            "native-decompile", ["rea", "decompile", native, "rea_leaf", *native_options]
        )
        assert "PI_RE_REA_SENTINEL" in decompiled["normalized_result"]
        run(
            "unknown-function",
            ["rea", "function", native, "missing_fixture_symbol", *native_options],
            expected=1,
        )
        malformed = home / "not-a-binary"
        malformed.write_text("Owned invalid binary fixture")
        run("malformed-target", ["rea", "function", malformed, "leaf", *native_options], expected=1)
        javascript = run(
            "javascript",
            [
                "rea",
                "analyze-javascript-application",
                ROOT / "tests/fixtures/pi-re-rea/javascript",
                "--json",
            ],
        )
        assert javascript["operation"] == "analyze_javascript_application"
        graph = javascript["normalized_result"]["graph"]
        assert graph["edges"]
        assert any(node["kind"] == "ipc-handler" for node in graph["nodes"])
        assert "rea:score" in json.dumps(graph)
        if apk:
            package = run("android-package", ["rea", "inspect-android-package", apk, "--json"])
            assert package["subject"]["digest"]["sha256"] == hashes[apk]
            assert "org.pi.re.fixture" in json.dumps(package["normalized_result"])
            classes = run(
                "android-classes", ["rea", "search-android-classes", apk, "MainActivity", "--json"]
            )
            assert "org.pi.re.fixture.MainActivity" in json.dumps(classes["normalized_result"])
            method = run(
                "android-method",
                [
                    "rea",
                    "inspect-android-method",
                    apk,
                    "org.pi.re.fixture.MainActivity",
                    "onCreate",
                    "--json",
                ],
            )
            assert method["operation"] == "inspect_android_method"
            assert "onCreate" in json.dumps(method["normalized_result"])
            refs = run(
                "android-references",
                [
                    "rea",
                    "trace-android-references",
                    apk,
                    "org.pi.re.fixture.MainActivity",
                    "--json",
                ],
            )
            assert refs["operation"] == "trace_android_references"
        blocked = run("setup-blocked", ["rea", "setup"], expected=1, structured=False)
        assert not blocked
        for name, flag in (
            ("update-flag-blocked", "--update"),
            ("hidden-update-blocked", "--incur-update-check"),
        ):
            blocked = run(name, ["rea", "providers", flag, "--json"], expected=1, structured=False)
            assert not blocked
        assert not (home / "data/pi-re/agent").exists(), "REA route touched agent initialization"
        for path, before in hashes.items():
            assert digest(path) == before, f"Original changed: {path}"
        residual = set(Path("/tmp").glob("rea-ghidra-*")) - runtime_before
        assert not residual, f"New Ghidra runtimes remain (check ownership): {residual}"
        print(
            json.dumps(
                {
                    "status": "passed",
                    "checks": checks,
                    "native_sha256": hashes[native],
                    "android_tested": bool(apk),
                    "originals_unchanged": True,
                    "new_ghidra_runtimes_remaining": 0,
                    "limits": "owned static fixtures only; no device/runtime/model qualification",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
