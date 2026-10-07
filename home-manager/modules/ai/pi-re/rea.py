"""Run the pinned REA static CLI with explicit engines and private profile state."""

import os
from pathlib import Path

from initialize import private_directory

# These operations inspect local inputs or write caller-selected derived evidence.
# Runtime/capture stays with pi-re's existing owned lab; package management stays Nix.
COMMANDS = frozenset(
    {
        "analyze",
        "inspect",
        "function",
        "search",
        "xrefs",
        "instructions",
        "decompile",
        "trace",
        "read-bytes",
        "providers",
        "capabilities",
        "doctor",
        "inspect-android-package",
        "search-android-classes",
        "inspect-android-class",
        "inspect-android-method",
        "trace-android-references",
        "analyze-javascript-application",
        "trace-application-feature",
        "inspect-artifact",
        "compare",
        "evidence-import",
        "evidence-export",
    }
)
HELP = frozenset({"--help", "-h", "--version", "-V"})


def command(config, locations, args, environment=None):
    """Return argv/env; reject unsupported routes before creating any state."""
    args = args or ["--help"]
    if args[0] not in COMMANDS | HELP:
        raise ValueError("REA route is not enabled; use pi-re rea --help for static analysis")
    forbidden = {"--mcp", "--update", "--incur-update-check"}
    if any(arg.split("=", 1)[0] in forbidden for arg in args):
        raise ValueError("REA MCP/update flags are disabled; Nix owns this static CLI")
    tools = config["rea"]
    cli = Path(tools["cli"])
    ghidra = Path(tools["ghidra"])
    jdk = Path(tools["jdk"])
    jar = Path(tools["jadxJar"])
    for executable in (
        cli,
        ghidra / "support/analyzeHeadless",
        jdk / "bin/java",
        jdk / "bin/javac",
    ):
        if not executable.is_absolute() or not os.access(executable, os.X_OK):
            raise ValueError(f"Pinned REA prerequisite unavailable: {executable}")
    if not jar.is_absolute() or not jar.is_file():
        raise ValueError("Pinned REA Android engine unavailable")
    root = locations["state"] / "rea"
    for directory in (root, root / "home", root / "config", root / "cache", root / "data"):
        private_directory(directory)
    env = dict(os.environ if environment is None else environment)
    for key in list(env):
        if key.startswith(("REA_", "HOPPER_")) or key in {
            "GHIDRA_INSTALL_DIR",
            "JAVA_HOME",
            "NODE_OPTIONS",
            "NODE_PATH",
            "_JAVA_OPTIONS",
            "JAVA_TOOL_OPTIONS",
            "JDK_JAVA_OPTIONS",
            "GHIDRA_JAVA_OPTIONS",
        }:
            del env[key]
    env.update(
        HOME=str(root / "home"),
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_CACHE_HOME=str(root / "cache"),
        XDG_DATA_HOME=str(root / "data"),
        XDG_STATE_HOME=str(root),
        # A short, whitespace-free parent is required by Ghidra's JVM argument parser.
        TMPDIR="/tmp",
        GHIDRA_INSTALL_DIR=str(ghidra),
        JAVA_HOME=str(jdk),
        REA_JADX_MCP_JAR=str(jar),
        REA_ANALYSIS_PROVIDER="auto",
        NO_UPDATE_NOTIFIER="1",
        PATH=f"{jdk / 'bin'}:{env.get('PATH', '')}",
    )
    return [str(cli), *args], env
