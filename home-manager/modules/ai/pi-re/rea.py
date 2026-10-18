"""Run pinned REA CLI/MCP with explicit engines and private profile state."""

import os
from pathlib import Path

from initialize import private_directory

# Release CLI inventory, excluding installers. Runtime routes require the same
# scope/ownership contract as ordinary Bash; Nix remains the package owner.
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
        "address-to-file-offset",
        "analyze-web-bundle",
        "annotate-native-function",
        "build-reconstruction-obligation-ledger",
        "capture-browser-scenario",
        "capture-electron-scenario",
        "capture-native-ui-scenario",
        "capture-process",
        "capture-web-screenshot",
        "compare-application-versions",
        "compare-bundles",
        "compare-javascript-export-shapes",
        "compare-managed-members",
        "compare-process-captures",
        "compare-source-to-bundle",
        "compare-web-captures",
        "compare-web-screenshots",
        "decode-android-resources",
        "decode-interface-builder",
        "decompile-jeb-item",
        "demangle-swift",
        "discover-webmcp-tools",
        "evaluate-reconstruction-coverage",
        "export-web-scripts",
        "extract-artifact",
        "extract-firmware",
        "import-managed-reconstruction",
        "import-reference-source",
        "inspect-analysis-view",
        "inspect-apktool-client",
        "inspect-asset-catalog",
        "inspect-binary-layout",
        "inspect-electron-page",
        "inspect-evidence-bundle",
        "inspect-evm-interface",
        "inspect-firmware-regions",
        "inspect-jeb-client",
        "inspect-keyed-archive",
        "inspect-macho",
        "inspect-managed-artifact",
        "inspect-managed-members",
        "inspect-managed-native-boundaries",
        "inspect-native-api",
        "inspect-native-data-type",
        "inspect-native-dispatch-metadata",
        "inspect-native-instruction",
        "inspect-native-load-image",
        "inspect-pe-resources",
        "inspect-plist",
        "inspect-recorded-crash",
        "inspect-signature",
        "inspect-web-event-listeners",
        "inspect-web-network-capture",
        "inspect-web-page",
        "list-architectures",
        "list-browser-targets",
        "list-electron-targets",
        "list-javascript-runtime-targets",
        "list-jeb-units",
        "observe-javascript-runtime",
        "observe-native-calls",
        "observe-native-ui",
        "observe-web-execution",
        "observe-web-session",
        "open-jeb-project",
        "project-android-application-graph",
        "project-apple-application-graph",
        "project-managed-application-graph",
        "reconcile-javascript-runtime",
        "recover-javascript-sources",
        "resolve-native-call-targets",
        "trace-dylib-resolution",
        "trace-javascript-semantics",
        "trace-native-ui-action",
        "trace-native-values",
        "trace-web-module-imports",
        "trace-web-source-location",
        "verify-managed-native-boundaries",
        "inspect-adb-client",
        "list-adb-devices",
        "inspect-adb-device",
        "list-adb-packages",
        "pull-adb-package",
        "read-adb-logcat",
        "inspect-adb-package",
        "pull-adb-file",
        "push-adb-file",
        "capture-adb-screen",
        "list-adb-processes",
        "list-adb-directory",
        "list-adb-features",
        "list-adb-services",
        "inspect-adb-display",
        "inspect-adb-window",
        "read-adb-setting",
        "collect-adb-bugreport",
        "resolve-adb-packages",
        "install-adb-package",
        "uninstall-adb-package",
        "start-adb-app",
        "start-adb-activity",
        "stop-adb-app",
        "search-bytes",
        "inspect-packet-fields",
        "inspect-packet-capture",
        "inspect-pcap-client",
        "inspect-pcap-capture",
        "inspect-signal-decoders",
        "decode-signal-recording",
        "compare-wasm-interfaces",
        "inspect-wasm-artifact",
        "inspect-sqlite-database",
        "inspect-go-binary",
        "inspect-rust-binary",
        "identify-flutter-build",
        "inspect-dart-aot",
        "inspect-electron-fuses",
        "project-harmony-application-graph",
        "inspect-with-objdump",
        "list-objdump-architectures",
        "list-cutter-sessions",
        "cutter-command",
        "execute-rizin-command",
        "debug-with-gdb",
        "debug-with-rizin",
        "list-frida-devices",
        "list-frida-processes",
        "instrument-with-frida",
    }
)
HELP = frozenset({"--help", "-h", "--version", "-V"})
# Caller-selected analysis data/timing, validated by upstream; never executable paths.
ANALYSIS_SETTINGS = frozenset(
    {
        "REA_GHIDRA_LANGUAGE_ID",
        "REA_GHIDRA_COMPILER_SPEC_ID",
        "REA_GHIDRA_SEED_FILE",
        "REA_GHIDRA_STARTUP_TIMEOUT_MS",
        "REA_GHIDRA_DISABLED_ANALYZERS",
    }
)


def command(config, locations, args, environment=None, *, mcp=False):
    """Return argv/env; the MCP transport accepts no caller-selected arguments."""
    if mcp:
        if args:
            raise ValueError("REA MCP transport takes no arguments")
        args = ["--mcp"]
    else:
        args = args or ["--help"]
        if args[0] not in COMMANDS | HELP:
            raise ValueError("REA route is not enabled; use pi-re rea --help")
        forbidden = {"--mcp", "--update", "--incur-update-check"}
        if any(arg.split("=", 1)[0] in forbidden for arg in args):
            raise ValueError("REA transport/update flags are disabled; Nix owns dependencies")
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
    settings = {key: env[key] for key in ANALYSIS_SETTINGS if key in env}
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
        PI_RE_STATE_DIR=str(locations["state"]),
        # A short, whitespace-free parent is required by Ghidra's JVM argument parser.
        TMPDIR="/tmp",
        GHIDRA_INSTALL_DIR=str(ghidra),
        JAVA_HOME=str(jdk),
        REA_JADX_MCP_JAR=str(jar),
        REA_ANALYSIS_PROVIDER="ghidra",
        **tools.get("environment", {}),
        NO_UPDATE_NOTIFIER="1",
        PATH=f"{jdk / 'bin'}:{env.get('PATH', '')}",
    )
    env.update(settings)
    return [str(cli), *args], env
