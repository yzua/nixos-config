# Android RE Tools

## MCP Analysis Servers

Two MCP servers load exclusively for this agent:

- **pyghidra-mcp** — headless Ghidra via PyGhidra: native `.so` decompilation,
  cross-refs, call graphs, symbol search
- **apktool-mcp-server** — APK decode/rebuild, smali and resource
  read/modify, project management

Shared MCP servers also available to this agent:

- **semgrep MCP** — structured Semgrep scans and rule/schema lookup through
  `semgrep mcp`
- **GitHub MCP** — repository, issue, PR, Actions, Dependabot, and code
  security context through the official `github-mcp-server`

MCP tools are discovered automatically at runtime. Use them as the primary
analysis interface whenever they cover the task. Fall back to bash `jadx` and
`apktool` CLI when MCP tools are unavailable or don't cover the need.

## Installed On This Machine

### Emulator and device control

- `adb` — Android Debug Bridge: install/uninstall apps, shell commands, file
  push/pull, port forwarding, logcat, process and package introspection
- `emulator` — QEMU-based Android emulator: boot AVDs, control snapshots,
  forward ports, configure network and display
- `avdmanager` — create, delete, and list Android Virtual Devices
- `sdkmanager` — install and update SDK packages, system images, build tools
- Android Studio — full IDE with layout inspector, profiler, device file
  explorer, and APK analyzer GUI

### Dynamic analysis

- `frida` / `frida-ps` (system `17.5.1`) — dynamic instrumentation toolkit:
  attach to running processes, inject JS hooks into Java and native layers,
  spawn apps with early hooks, trace function calls and modify return values
  at runtime
- rooted AVD with unattended `su 0 ...` — Magisk-rooted emulator with
  shell-root that does not prompt for authorization

### Proxy and network interception

- `mitmproxy` / `mitmdump` / `mitmweb` — interactive HTTPS proxy:
  intercept, inspect, modify, and replay HTTP(S) traffic; `mitmdump` for
  headless capture, `mitmweb` for browser UI, `mitmproxy` for terminal UI
- `tshark` — CLI network protocol analyzer (Wireshark engine): capture and
  decode packets, filter by protocol/field, export to PCAP for deeper analysis
- `httpx` — fast HTTP prober: enumerate live hosts, extract titles/status
  codes/technologies from URLs, check for open ports and response headers
- `katana` — web crawler/spider: discover URLs, endpoints, and JavaScript
  files from web applications, useful for mapping API surfaces and hidden paths
- `amass` — DNS enumeration and network mapping: discover subdomains, DNS records,
  and infrastructure belonging to the target's backend services

### Network scanning

- `nmap` — port scanning and service fingerprinting: discover open ports, running
  services, and OS detection on backend servers discovered during traffic analysis
- `masscan` — fast port scanner: internet-scale port scanning for rapid
  discovery of open ports across large IP ranges; useful for scanning backend
  servers discovered during traffic analysis

### Backend and vulnerability scanning

- `nuclei` — template-based vulnerability scanner: fast detection of known
  CVEs, misconfigurations, exposed panels, and default credentials using
  community templates; useful for scanning backend endpoints discovered
  during traffic analysis
- `subfinder` — subdomain discovery tool: find subdomains from passive DNS
  sources; useful for mapping backend service infrastructure
- `whatweb` — web technology fingerprinter: identify server software,
  frameworks, and technologies on backend endpoints
- `interactsh` — OOB interaction server (ProjectDiscovery): detect blind
  vulnerabilities (blind SSRF, blind XSS, blind command injection) by
  monitoring DNS, HTTP, and HTTPS callback requests from the target
- `testssl` — TLS testing tool: comprehensive SSL/TLS cipher, protocol,
  and certificate analysis against backend HTTPS endpoints; checks for
  Heartbleed, POODLE, CRIME, and other known TLS vulnerabilities

### Static analysis

- `jadx` (includes `jadx-gui`) — Dex-to-Java decompiler: convert DEX bytecode
  to readable Java source, inspect AndroidManifest, search classes/methods/strings
- `apkid` — identify APK packers, protectors, compilers, and obfuscators before
  choosing a decompilation strategy
- `apktool` — APK decode and rebuild: extract smali bytecode, resources, and
  manifest; modify and repackage APKs (patching, resource editing, smali changes)
- `radare2` — CLI reverse engineering framework: disassemble, analyze, and
  debug native binaries; inspect ELF headers, sections, symbols, and cross-refs
- `rizin` — modern reverse engineering framework for disassembly, analysis,
  binary metadata, and scripted native inspection
- `cutter` — GUI frontend for radare2: visual disassembly, graphs, hex editor,
  decompilation view for native binary analysis
- `ghidra-bin` — NSA reverse engineering suite: `analyzeHeadless` for scripted
  batch analysis, `ghidraRun` for GUI; powerful decompiler, type inference,
  and plugin ecosystem for native RE
- `binwalk` — firmware/binary analysis tool: scan for embedded files,
  signatures, and compressed data; extract filesystems and hidden payloads
  from APKs and native binaries
- `semgrep` — static analysis with pattern-matching and taint-tracking rules:
  scan jadx output for SQL injection, hardcoded secrets, weak crypto, path
  traversal, TLS bypass, and Android-specific vulnerability patterns without
  requiring a build. Install with `pip install --user semgrep`. See
  SEMGREP-GUIDE.md for setup, commands, and custom Android rules.
- `codeql` — deep semantic code analysis with full taint tracking and dataflow
  path validation. Use when Semgrep cannot resolve ambiguous dataflow or you
  need to prove a specific source-to-sink path. Requires compilable source or
  jadx output for structural analysis. See CODEQL-GUIDE.md for setup, database
  creation, and custom Android queries.
- `afl++` — coverage-guided binary fuzzer for native `.so` libraries. Fuzz JNI
  entry points, protobuf parsers, and custom protocol handlers. Supports QEMU
  mode for binary-only fuzzing. See NATIVE-FUZZING.md for corpus generation,
  harness construction, and crash analysis.
- `yara` — pattern matching engine: write and apply YARA rules to detect
  malware signatures, hardcoded patterns, and suspicious code in APKs and
  native libraries

### Binary analysis

- `checksec` — binary security property checker: verify NX, PIE, RELRO,
  stack canaries, and Fortify Source on native `.so` libraries extracted
  from APKs
- `objdump` — disassembler (from binutils via gcc package): disassemble
  native `.so` files, inspect ELF sections, symbols, and relocations
- `readelf` — ELF analyzer (from binutils via gcc package): inspect ELF
  headers, sections, segments, dynamic symbols, and note sections of
  native libraries
- `nm` — symbol listing (from binutils via gcc package): list symbols from
  native `.so` files to identify JNI entry points and exported functions

### Web app testing

- `ffuf` — fast web fuzzer: brute-force directories, files, parameters, and
  virtual hosts; useful for discovering hidden endpoints and API routes
- `dalfox` — XSS scanner: detect and verify cross-site scripting
  vulnerabilities in web endpoints discovered during traffic analysis
- `arjun` — HTTP parameter discovery: find hidden query parameters, headers,
  and JSON fields that the server accepts; useful for mapping API attack surface
- `zap` — OWASP ZAP web proxy/scanner: automated and manual security testing
  for web applications, active/passive scanning, spidering, and fuzzing

### Android build tools

- `aapt` / `aapt2` — Android Asset Packaging Tool: compile resources,
  inspect APK contents, dump manifest and resource tables from compiled apps
- `apksigner` — sign and verify APK signatures; re-sign modified APKs for
  installation after patching
- `zipalign` — align APK entries on 4-byte boundaries (required before
  signing for optimal runtime performance)

### Runtime instrumentation

- `objection` — Frida-powered runtime exploration toolkit: bypass SSL pinning,
  dump credentials, explore filesystem and SQLite databases, disable root
  detection, and inspect classes/methods without writing raw Frida scripts

### Python RE libraries

- `androguard` — Python APK analysis library: parse AndroidManifest, DEX
  bytecode, certificates, and resources programmatically; extract permissions,
  activities, services, strings, and class information without external tools
- `z3-solver` (Python) — SMT constraint solver: analyze cryptographic
  constraints, verify security property assumptions, and solve key
  generation logic; useful for validating dataflow path feasibility
- `cyberchef` — universal data transformation tool (via `cyberchef` CLI or
  browser): encode/decode/hash/encrypt/compress data, convert between formats,
  analyze base64/hex/JWT tokens captured during testing
- `jwt-cli` — decode, verify, and craft JWTs during auth and session testing
- `step-cli` — inspect X.509 certificates, OAuth/OIDC metadata, JWTs, and
  trust-chain material

### Device UI automation

- `agent-device` — structured accessibility-tree device interaction: open
  apps, take snapshots, click/fill UI elements by ref or label, take
  screenshots. Load the `agent-device` skill before use

### Utility tools

- `sqlite3` — query and inspect SQLite databases extracted from app data
  directories (tokens, cached data, local storage)
- `scrcpy` — mirror and control Android device display from the host; useful
  for observing app behavior visually during dynamic analysis
- `unzip`, `xz` — extract and decompress APK contents, native libraries, and
  archived data
- `httpie` (`http` command) — human-friendly HTTP client: explore APIs interactively
  with syntax-highlighted output, session management, and authentication helpers;
  easier than curl for ad-hoc API testing during traffic analysis

### Supply chain scanning

- `trivy` — vulnerability and secret scanner: scan APKs, native libraries,
  and container images for known CVEs, misconfigurations, and embedded secrets
- `osv-scanner` — OSV-backed dependency vulnerability scanning for extracted
  projects, lockfiles, and source trees
- `syft` — generate SBOMs from extracted source trees, containers, and
  filesystems
- `grype` — scan SBOMs, containers, and filesystems for known vulnerabilities

### Code coverage

- `gcovr` — code coverage report generator: generate coverage reports for
  native code fuzzing sessions (see NATIVE-FUZZING.md), visualize which
  code paths AFL++ exercised

## Tool Selection Guide

Use the smallest tool that gives a reliable answer:

- **Need package identity / version / paths / ABI?** Use `adb` and `dumpsys`
- **Need exported components or suspicious strings?** Use `re-static.sh`, `jadx`,
  `apktool`
- **Need packer/protector clues?** Use `apkid` before deep decompilation
- **Need to confirm live traffic?** Use `mitmdump` via the tmux `mitm` pane
- **Need runtime values or bypasses?** Use Frida attach or spawn
- **Need to click through the app reliably?** Use `agent-device`
- **Need repeated proof?** Write a small Bash/Python/Node/Bun/Frida script
- **Need to scan source for vulnerability patterns?** Use `semgrep --config auto`
- **Need deep taint tracking on a specific path?** Use `codeql database analyze`
- **Need to fuzz native .so libraries?** Use `afl++` with QEMU mode
- **Need to scan backend endpoints for known CVEs?** Use `nuclei`
- **Need to find backend subdomains or services?** Use `subfinder`, `amass`
- **Need to test for blind vulnerabilities?** Use `interactsh`
- **Need to check TLS configuration?** Use `testssl`
- **Need to analyze binary security properties?** Use `checksec`, `readelf`
- **Need to match patterns in binary data?** Use `yara`
- **Need to scan for CVEs in dependencies?** Use `trivy`, `osv-scanner`,
  `syft`, `grype`
- **Need to check fuzzing code coverage?** Use `gcovr`

## Fast Vulnerability Playbooks

### Exported component abuse

Goal: prove whether another app or shell-level attacker can reach privileged
behavior.

Start with:

```bash
adb shell dumpsys package com.example.target | rg 'exported=|Activity|Service|Receiver|Provider'
adb shell cmd package resolve-activity --brief -c android.intent.category.LAUNCHER com.example.target
```

Then try the smallest attacker-style invocation you can justify:

```bash
adb shell am start -n com.example.target/.SomeActivity
adb shell am startservice -n com.example.target/.SomeService
adb shell am broadcast -n com.example.target/.SomeReceiver
adb shell content query --uri content://com.example.target.provider/
```

Proof target:

- unauthorized action
- sensitive data exposure
- privileged flow without intended caller checks

### Deep link abuse

Goal: prove whether attacker-controlled URLs can drive privileged or unsafe app
behavior.

```bash
adb shell dumpsys package com.example.target | rg 'VIEW|BROWSABLE|scheme|host|path'
adb shell am start -a android.intent.action.VIEW -d 'app://host/path?x=1' com.example.target
```

Look for:

- auth state confusion
- hidden screen reachability
- open redirect behavior
- WebView reachability
- attacker-controlled parameters flowing into privileged actions

### Local storage triage

Goal: prove what secrets or attacker-useful state live on device.

```bash
adb shell 'run-as com.example.target ls -R files shared_prefs databases 2>/dev/null'
adb shell 'run-as com.example.target cat shared_prefs/*.xml 2>/dev/null'
adb shell 'run-as com.example.target sqlite3 databases/app.db ".tables" 2>/dev/null'
adb shell 'su 0 find /data/data/com.example.target -maxdepth 3 | head -100'
```

Proof target:

- reusable tokens
- credentials or API keys
- locally cached sensitive objects
- weak device binding or trust assumptions

### Auth / replay / IDOR testing

Goal: convert captured traffic into attacker-usable proof.

```bash
tmux capture-pane -t android-re:mitm -p -S -300 | grep -iE 'authorization|bearer|token|cookie'
tmux capture-pane -t android-re:mitm -p -S -300 | grep -oP '(?:GET|POST|PUT|DELETE|PATCH) https?://[^ ]+'
```

Then move to a script or `curl` replay that changes one thing at a time:

- object ID
- account ID
- device identifier
- timestamp / nonce assumptions
- headers that look like soft binding rather than hard proof

Do not claim replay or IDOR until the modified request proves unauthorized reach.

## Tmux Session Layout

`re-avd.sh start` creates a tmux session called `android-re` with these windows:

| Window | Name     | Purpose                           |
| ------ | -------- | --------------------------------- |
| 0      | `shell`  | General shell, `adb` commands     |
| 1      | `mitm`   | `mitmdump` live traffic capture   |
| 2      | `frida`  | Frida REPL / hook output          |
| 3      | `logs`   | `tail -f` emulator runtime log    |
| 4      | `logcat` | `adb logcat -b all -v threadtime` |

### Reading tmux panes from the agent

You cannot attach interactively from the agent. Capture pane output instead:

```bash
tmux capture-pane -t android-re:mitm -p -S -80
tmux capture-pane -t android-re:logcat -p -S -80
tmux capture-pane -t android-re:frida -p -S -80
tmux capture-pane -t android-re:logs -p -S -80
tmux capture-pane -t android-re:shell -p -S -80
```

### Sending commands to tmux panes

```bash
tmux send-keys -t android-re:mitm C-c
tmux send-keys -t android-re:mitm "clear" Enter
tmux send-keys -t android-re:mitm "mitmdump --set confdir=$HOME/Downloads/android-re-tools/custom-ca --listen-host 0.0.0.0 --listen-port 8084 --set flow_detail=2" Enter

tmux send-keys -t android-re:frida "frida -U -n com.example.target" Enter
tmux capture-pane -t android-re:frida -p -S -60
```

## Static Triage Recipes

### Extract and inventory an APK

```bash
bash scripts/ai/android-re/re-static.sh prepare /path/to/app.apk
bash scripts/ai/android-re/re-static.sh inventory
```

### Search by investigative goal

```bash
# Network stack and HTTP clients
grep -R "okhttp\|retrofit\|cronet\|quic" ~/.cache/android-re/out/<app>/jadx

# Trust and pinning
grep -R "TrustManager\|CertificatePinner\|X509TrustManager" ~/.cache/android-re/out/<app>/jadx

# Root / emulator / Frida detection
grep -R "frida\|magisk\|su\|test-keys\|ro.debuggable\|emulator\|qemu" ~/.cache/android-re/out/<app>/jadx

# Interesting exported components and deeplinks
grep -R "android.intent.action.VIEW\|BROWSABLE\|exported=\"true\"" ~/.cache/android-re/out/<app>
```

### Semgrep scan of jadx output

```bash
# Install if needed
pip install --user semgrep

# Scan with community rules (fast)
semgrep --config auto ~/.cache/android-re/out/<app>/jadx/sources/ --text

# JSON output for automated processing
semgrep --config auto --json ~/.cache/android-re/out/<app>/jadx/sources/ \
  -o ~/Documents/<app>/analysis/semgrep-results.json

# Review findings
cat ~/Documents/<app>/analysis/semgrep-results.json | jq '.results[] | {rule: .check_id, file: .path, line: .start.line, message: .extra.message}'
```

Validate each Semgrep finding with the dataflow framework in
DATAFLOW-VALIDATION.md before investing in PoC development.

### CodeQL deep analysis of jadx output

```bash
# Create database (structural analysis — taint tracking limited without build)
codeql database create ~/Documents/<app>/analysis/codeql-db \
  --language=java \
  --source-root=~/.cache/android-re/out/<app>/jadx/sources/ \
  --overwrite

# Run all security queries
codeql database analyze ~/Documents/<app>/analysis/codeql-db \
  codeql/java-queries:Security \
  --format=sarif-latest \
  --output=~/Documents/<app>/analysis/codeql-results.sarif

# Review results
cat ~/Documents/<app>/analysis/codeql-results.sarif | \
  jq '.runs[].results[] | {rule: .ruleId, location: .locations[0].physicalLocation.artifactLocation.uri, line: .locations[0].physicalLocation.region.startLine}'
```

See CODEQL-GUIDE.md for custom Android taint-tracking queries.

### AFL++ fuzzing of native libraries

```bash
# Identify target functions
nm -D ~/Documents/<app>/analysis/native-libs/libtarget.so | grep -iE 'Java_|JNI_'
strings ~/Documents/<app>/analysis/native-libs/libtarget.so | grep -iE 'parse|decode|read'

# Generate smart corpus (see NATIVE-FUZZING.md for full script)
strings -n 4 ~/Documents/<app>/analysis/native-libs/libtarget.so | \
  grep -iE '<|>|xml|json|http' | sort -u \
  > ~/Documents/<app>/analysis/native-strings-formats.txt

# Run AFL++ in QEMU mode
afl-fuzz -i ~/Documents/<app>/analysis/fuzz-corpus/ \
  -o ~/Documents/<app>/analysis/fuzz-findings/ \
  -- ./harness @@
```

See NATIVE-FUZZING.md for harness construction, crash triage, and ASan integration.

### What static analysis should answer

- is networking Java, native, or mixed
- where auth and token code likely lives
- whether pinning appears standard or custom
- whether detection is likely Java-only or native-backed
- whether the package ships significant native libraries

### Native triage cues

Pivot early to native review when static output shows:

- `libcronet`, `cronet`, `boringssl`, `ssl`, `conscrypt`, or custom TLS wrappers
- JNI methods around auth, trust, crypto, or device checks
- large `.so` files owning request construction or anti-analysis
- Java wrappers with little logic beyond `native` declarations

## Low-Level Android Commands

```bash
# Runtime permissions (app ops)
adb shell cmd appops get com.example.target
adb shell cmd appops set com.example.target RUN_IN_BACKGROUND allow

# Full package dump (more detail than dumpsys package)
adb shell pm dump com.example.target | head -200

# Content provider method calls (beyond query)
adb shell content call --uri content://com.example.target.provider/data --method getData

# Device settings inspection
adb shell settings list global
adb shell settings list secure
adb shell settings list system

# App standby buckets and battery optimization
adb shell am get-standby-bucket com.example.target
adb shell dumpsys batteryopt
```

## APK Version Diff

Compare two versions of the same app:

```bash
bash scripts/ai/android-re/re-static.sh prepare old_version.apk
bash scripts/ai/android-re/re-static.sh prepare new_version.apk
bash scripts/ai/android-re/re-static.sh diff old_version new_version
```

Shows: hash changes, manifest permission changes, new/removed native libraries,
Java class count differences.

## Backup Extraction Testing

```bash
# Test if backup is allowed
adb backup -f /tmp/target.ab com.example.target
# If the app allows backup, extract it:
dd if=/tmp/target.ab bs=1 skip=24 | python3 -c "import zlib,sys; sys.stdout.buffer.write(zlib.decompress(sys.stdin.buffer.read()))" | tar xf -
# Or use Android backup extractor
# Check manifest for: android:allowBackup, android:fullBackupContent
grep -i "allowBackup\|fullBackupContent" ~/.cache/android-re/out/<app>/apktool/AndroidManifest.xml
```

If `allowBackup=false`, fall back to root extraction:

```bash
adb shell "su 0 tar -cf - /data/data/com.example.target" | tar xf -
```

## JWT and Token Analysis

```bash
# Decode JWT without verification
python3 -c "import jwt,sys; t=sys.argv[1]; print(jwt.decode(t,options={'verify_signature':False}))" "eyJ..."

# Check token structure (header, payload, signature)
echo "eyJ..." | cut -d. -f1 | base64 -d 2>/dev/null
echo "eyJ..." | cut -d. -f2 | base64 -d 2>/dev/null
```

Common token weaknesses to check:

- algorithm confusion (`"alg":"none"`, RS256 vs HS256)
- missing or weak `exp`/`nbf` claims
- sensitive data in payload (PII, internal IDs)
- predictable or sequential token values
- missing issuer/audience binding
- token replay across devices or sessions

## Firebase and Cloud Service Triage

```bash
# Check for Firebase config
grep -r "firebase\|google-services\|google_app_id\|google_api_key\|project_info" ~/.cache/android-re/out/<app>/apktool/res/
find ~/.cache/android-re/out/<app> -name "google-services.json" -o -name "google-services.xml"

# Test misconfigured Firebase Realtime Database (unauthenticated access)
http GET "https://<project-id>.firebaseio.com/.json"
http PUT "https://<project-id>.firebaseio.com/test.json" <<< '{"test":true}'

# Check Google API key restrictions
http GET "https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=<key>"
```

## Non-HTTP Protocol Handling

### WebSocket

```bash
# mitmproxy captures WebSocket by default — read from the mitm pane
# For manual testing:
websocat wss://target.example.com/ws
```

### gRPC

```bash
# Check for gRPC/protobuf in static analysis
grep -r "grpc\|protobuf\|\.proto" ~/.cache/android-re/out/<app>/jadx
find ~/.cache/android-re/out/<app> -name "*.proto" -o -name "*grpc*"

# Probe gRPC services (if grpcurl is available)
grpcurl -plaintext target.example.com:443 list
grpcurl -plaintext target.example.com:443 list package.Service
```

### Protobuf decoding

If traffic contains protobuf but is not decoded:

```bash
# Extract raw protobuf from mitmproxy dump and decode with protoc
protoc --decode_raw < binary_data
```

## Encrypted/Packed DEX Detection

Signs of packed or encrypted DEX:

- `jadx` output shows very few classes or a single wrapper class
- App uses `DexClassLoader` or `InMemoryDexClassLoader` at runtime
- `binwalk` shows embedded DEX inside assets or other files
- Native library responsible for class loading

Dump unpacked DEX at runtime:

```bash
# Hook DexClassLoader to capture dynamically loaded code
frida -U -n com.example.target -q -e '
Java.perform(function(){
  var DexClassLoader = Java.use("dalvik.system.DexClassLoader");
  DexClassLoader.$init.implementation = function(dexPath,optimizedDir,libPath,parent){
    console.log("[dex-classloader] " + dexPath);
    return this.$init(dexPath,optimizedDir,libPath,parent);
  };
});
'
```

## Magisk/Zygisk Advanced Bypass

When standard Frida hooks and Java-layer spoofing are insufficient:

```bash
# Check Magisk DenyList
adb shell "su 0 magisk --denylist ls"

# Add target to DenyList (hides root from the app)
adb shell "su 0 magisk --denylist add com.example.target"

# Enable Zygisk in Magisk settings (requires Magisk Delta or 24+)
# Then install Shamiko module for comprehensive root hiding
# Shamiko hides: Magisk binary, su binary, Magisk mount points, Zygisk traces
```

Zygisk-based hiding is stronger than Java-layer hooks because it operates before
the app process starts. Use when:

- Java hooks fire but app still detects root/emulator
- The app uses native root checks (not Java File.exists)
- The app checks for Magisk-specific artifacts (mount points, binaries)

## mitmproxy Practical Usage

### Architecture

- `mitmdump` runs in tmux window `android-re:mitm`
- config dir: `~/Downloads/android-re-tools/custom-ca/`
- default listen: `0.0.0.0:8084`
- CA cert is injected into Android 14's conscrypt namespace on
  `re-avd.sh start`

### Enable / disable proxy

```bash
bash scripts/ai/android-re/re-avd.sh proxy-set 10.0.2.2:8084 --block-quic
bash scripts/ai/android-re/re-avd.sh proxy-clear
adb shell settings get global http_proxy
```

Expected when enabled:

```text
10.0.2.2:8084
```

### Read captured traffic

```bash
tmux capture-pane -t android-re:mitm -p -S -300
tmux capture-pane -t android-re:mitm -p -S -300 | grep -oP '(?:GET|POST|PUT|DELETE|PATCH|HEAD) https?://[^ ]+' | sort -u
tmux capture-pane -t android-re:mitm -p -S -300 | grep 'POST https'
tmux capture-pane -t android-re:mitm -p -S -300 | grep '<< HTTP'
tmux capture-pane -t android-re:mitm -p -S -300 | grep -iE 'authorization|bearer|x-api-key|token'
```

### Interpret common output

- visible decrypted requests -> interception is working
- `Client TLS handshake failed` -> trust failure or pinning
- `client disconnected` -> app retrying, rejecting, or partially bypassing
- no output at all -> proxy not set, app not restarted, Cronet/native bypass, or
  app not making requests yet

Do not call it "pinning" until proxy state, listener state, restart, and actual
network exercise have all been proven.

### Restart mitmdump with different options

```bash
tmux send-keys -t android-re:mitm C-c
sleep 1
tmux send-keys -t android-re:mitm "mitmdump --set confdir=$HOME/Downloads/android-re-tools/custom-ca --listen-host 0.0.0.0 --listen-port 8084 --set flow_detail=3" Enter
```

## Frida Practical Usage

## Local Frida Hook Library

Use the local hook library before writing one-off hooks from scratch. The goal
is to get quick proof, then adapt only when the target requires it.

Available scripts under `scripts/ai/android-re/`:

- `frida-hook-build-fields.js` — log `android.os.Build.*` values seen by the app
- `frida-hook-file-exists.js` — log root/emulator/frida file probes
- `frida-hook-shared-prefs.js` — log SharedPreferences reads and writes
- `frida-hook-url-log.js` — log URL construction and common OkHttp request URLs
- `frida-bypass-certificate-pinner.js` — bypass common OkHttp and Conscrypt trust checks
- `frida-spoof-build.js` — spoof Java-layer Build fields and hide emulator file paths
- `frida-hook-crypto.js` — log javax.crypto.Cipher, Mac, MessageDigest, Signature
  operations (algorithm, input/output size, digest hex)
- `frida-hook-webview.js` — log WebView.loadUrl, evaluateJavascript,
  addJavascriptInterface, shouldOverrideUrlLoading, setJavaScriptEnabled
- `frida-hook-network.js` — log Socket.connect (host:port), SSLSocket.startHandshake,
  OkHttp RealCall.execute, HttpURLConnection.connect
- `frida-hook-intent.js` — log startActivity, BroadcastReceiver.onReceive,
  ContentResolver.query with action, data URI, and extras keys

Example usage:

```bash
frida -U -n com.example.target -l scripts/ai/android-re/frida-hook-build-fields.js -q
frida -U -n com.example.target -l scripts/ai/android-re/frida-hook-url-log.js -q
frida -U -f com.example.target -l scripts/ai/android-re/frida-bypass-certificate-pinner.js
```

Rule:

- start with a local reusable hook to confirm the right layer and data path
- when a reusable hook proves the target has interesting behavior at that layer,
  write a target-specific hook immediately — do not hesitate or ask for permission
- combine multiple hooks: `frida -U -n TARGET -l hook1.js -l hook2.js -l hook3.js`
- save target-specific hooks to `~/Documents/{app}/scripts/`

## Writing Custom Hooks

You should write custom Frida hooks whenever you need to intercept a specific
class, method, or behavior that the built-in library does not cover. This is
normal RE work — do it freely.

When to write a custom hook:

- you found an interesting class or method in static analysis and want to trace
  its arguments or return values at runtime
- you need to bypass a specific check (root, pinning, emulator, integrity) that
  the generic bypass hooks do not cover
- you want to dump the output of a crypto operation, token generation, or auth
  flow to understand what the app computes
- you need to modify a return value to unlock a guarded code path

How to write one quickly:

```bash
# Inline one-liner probe
frida -U -n com.example.target -q -e '
Java.perform(function(){
  var Cls = Java.use("com.target.SomeClass");
  Cls.someMethod.implementation = function(a, b) {
    console.log("[custom] someMethod(" + a + ", " + b + ") = " + this.someMethod(a, b));
    // or to bypass: return true;
  };
});
'

# Save to a file for reuse
cat > ~/Documents/{app}/scripts/hook-some-method.js << 'EOF'
Java.perform(function () {
    var Cls = Java.use("com.target.SomeClass");
    Cls.someMethod.implementation = function (a, b) {
        var result = this.someMethod(a, b);
        console.log("[custom] someMethod(" + a + ", " + b + ") = " + result);
        return result;
    };
    console.log("[custom] Hook active for SomeClass.someMethod");
});
EOF
frida -U -n com.example.target -l ~/Documents/{app}/scripts/hook-some-method.js -q
```

## External Research For Hooks And Bypass Techniques

When you hit a wall — a specific anti-analysis technique, a custom pinning
implementation, an unfamiliar SDK, or a detection method you have not seen
before — search aggressively:

- **GitHub**: search for `<app-name> frida hook`, `<sdk-name> bypass`, `android
<technique> bypass frida`, or the exact class/method name you are trying to
  hook. Other researchers often publish hooks for popular apps and SDKs.
- **Web/CVE databases**: search for CVEs affecting SDKs found in the target,
  known bypass techniques for specific anti-analysis products, and security
  blog writeups about comparable apps.
- **Frida code snippets**: search for `frida Java.use` plus the class name, or
  browse Frida scripts repos for patterns you can adapt.

Always validate external hooks and techniques against the actual target before
trusting them. Adapt, don't copy blindly.

External research is allowed when local paths are insufficient:

- search GitHub for similar apps, bypass hooks, or reverse-engineering notes
- search advisories and CVE writeups for vulnerable libraries, SDKs, WebViews,
  auth components, and mobile frameworks seen in the target
- use external results to generate hypotheses, then verify them locally against
  the target before treating them as findings

### Version rules

- system Frida: `17.5.1`
- server binary:
  `~/Downloads/android-re-tools/frida/frida-server-17.5.1-android-x86_64`
- remote path: `/data/local/tmp/frida-server-17.5.1`
- do not use the broken legacy `16.4.10` virtualenv

### Start and verify server

```bash
bash scripts/ai/android-re/re-avd.sh frida-start
frida --version
frida-ps -U | head -20
adb shell "su 0 sh -c 'ps -A | grep frida'"
adb shell "su 0 sh -c 'tail -20 /data/local/tmp/frida.log'"
```

### Attach modes

```bash
# Running process
frida -U -n com.example.target

# PID attach
frida -U -p 1234

# One-shot inline probe
frida -U -n com.example.target -q -e 'console.log("attached")'

# Script file
frida -U -n com.example.target -l /tmp/hook.js -q

# Spawn mode for early bypasses
frida -U -f com.example.target -l /tmp/hook.js

# Translated or emulated code path
frida -U -n com.example.target --realm=emulated
```

### Quick inline hooks

```bash
# What Build fields does the app see?
frida -U -n com.example.target -q -e '
Java.perform(function() {
  var B = Java.use("android.os.Build");
  console.log("MODEL=" + B.MODEL.value);
  console.log("HARDWARE=" + B.HARDWARE.value);
  console.log("MANUFACTURER=" + B.MANUFACTURER.value);
  console.log("BRAND=" + B.BRAND.value);
  console.log("DEVICE=" + B.DEVICE.value);
  console.log("FINGERPRINT=" + B.FINGERPRINT.value);
});
'

# Log Java URL creation
frida -U -n com.example.target -q -e '
Java.perform(function() {
  var URL = Java.use("java.net.URL");
  URL.$init.overload("java.lang.String").implementation = function(url) {
    console.log("[URL] " + url);
    return this.$init(url);
  };
});
'

# Basic root-file bypass
frida -U -n com.example.target -q -e '
Java.perform(function() {
  var File = Java.use("java.io.File");
  File.exists.implementation = function() {
    var path = this.getAbsolutePath();
    if (path.indexOf("su") >= 0 || path.indexOf("magisk") >= 0 || path.indexOf("supersu") >= 0) {
      console.log("[ROOT-BYPASS] " + path + " -> false");
      return false;
    }
    return this.exists();
  };
});
'
```

### When to pivot away from Java hooks

Pivot to native analysis when:

- static analysis shows JNI-heavy auth or trust logic
- Frida Java hooks only hit wrappers
- the app uses Cronet, BoringSSL, or native TLS
- URL logging sees nothing but traffic clearly exists
- pinning bypass attempts do not change behavior

### Logcat triage by symptom

Use logcat as evidence, not background noise. Prioritize strings around:

- SSL / TLS / handshake / trust / cert
- root / emulator / tamper / integrity
- okhttp / cronet / quic / socket
- WebView / chromium / bridge
- crash stack traces tied to first launch or guarded screens

## agent-device Practical Usage

### Always load the skill first

The `agent-device` skill provides the canonical command reference. Load it
before any UI interaction. This is not optional — the skill provides the
canonical command reference and argument syntax.

### agent-device is the primary dynamic analysis tool

Use `agent-device` as the primary way to interact with the app during dynamic
analysis. It replaces manual `adb shell input tap` with structured,
reproducible, accessibility-tree-based interaction that survives layout changes.

When doing dynamic analysis, your default loop should be:

1. `agent-device snapshot -i` — read the current screen
2. pick an element to interact with
3. `agent-device click @eN` or `agent-device fill @eN "value"` — act
4. `agent-device snapshot -i` — read the result
5. `agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/name.png`
6. read mitm + logcat + Frida panes for what happened
7. repeat for every reachable element on the screen

### Core workflow

```bash
agent-device devices --platform android
agent-device open com.example.target --platform android
agent-device snapshot -i
agent-device click @e3
agent-device fill @e5 "user@example.com"
agent-device find "Settings" click
agent-device screenshot --out /tmp/screen.png
agent-device close
```

### Systematic screen exploration

For each screen you reach, follow this pattern:

```bash
# Open the app
agent-device open com.example.target --platform android

# Snapshot the current screen
agent-device snapshot -i

# Click every clickable element, one at a time
# For each element:
agent-device click @e3
agent-device snapshot -i
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/tab-name.png

# Navigate back if you left the current screen
agent-device press Back

# Fill every input field
agent-device fill @e7 "test-input-value"

# Move to next screen
agent-device find "Next" click
```

### Combining with network and hook monitoring

The most powerful dynamic analysis combines `agent-device` with live traffic
and hook monitoring in a tight loop:

```bash
# Terminal 1: Start Frida hooks
frida -U -n com.example.target -l scripts/ai/android-re/frida-hook-network.js -l scripts/ai/android-re/frida-hook-url-log.js -q &

# Terminal 2: agent-device exploration
agent-device open com.example.target --platform android
agent-device snapshot -i
# ... click through screens ...
# After each action, read the traffic:
tmux capture-pane -t android-re:mitm -p -S -40
tmux capture-pane -t android-re:frida -p -S -40
```

### Screenshot naming convention

Save screenshots with descriptive names for evidence:

```bash
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/01-launch.png
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/02-login-form.png
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/03-after-login.png
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/04-profile.png
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/05-settings.png
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/06-search-results.png
```

### When agent-device is not enough

`agent-device` handles accessibility-tree interaction. Use `adb` directly for:

- `adb shell input keyevent KEYCODE_BACK` — navigate back (or `agent-device press Back`)
- `adb shell am start` — launch specific activities via intent
- `adb shell content query` — query content providers
- `adb shell pm clear` — clear app data between test rounds
- `adb shell settings put` — modify system settings
- `adb logcat` — continuous log monitoring in tmux

### Rules

- always `snapshot -i` before interacting
- re-snapshot after any UI change (refs invalidate)
- prefer refs (`@eN`) over coordinates
- use `find "label" click` for semantic lookup
- take screenshots at every significant state change
- correlate each UI action with network and hook output
- do not skip screens — exercise every reachable element

## adb Quick Reference

```bash
adb devices -l
adb shell getprop sys.boot_completed
adb install -r /path/to/app.apk
adb shell pm path com.example.target
adb shell pidof com.example.target
adb shell dumpsys package com.example.target | grep versionName
adb shell am force-stop com.example.target
adb shell monkey -p com.example.target -c android.intent.category.LAUNCHER 1
adb shell 'su 0 sh -c id'
adb shell getenforce
adb push local.txt /data/local/tmp/
adb pull /data/local/tmp/file.txt ./
adb forward tcp:8080 tcp:8080
```

## Device Spoofing

- applied automatically on `re-avd.sh start`
- re-apply manually: `bash scripts/ai/android-re/re-avd.sh spoof`
- restore hidden files: `bash scripts/ai/android-re/re-avd.sh unspoof`
- Java `android.os.Build.*` fields may still expose emulator values because of
  Zygote caching

Use the Frida build spoof script when Java-level identity still leaks:

```bash
frida -U -f com.example.target -l scripts/ai/android-re/frida-spoof-build.js
frida -U -n com.example.target -l scripts/ai/android-re/frida-spoof-build.js
```

## Scripting And POC Development

You are expected to write and run custom scripts to validate findings. This is
core RE work.

### Available runtimes

| Runtime  | Version | Good for                                                 |
| -------- | ------- | -------------------------------------------------------- |
| Bash     | 5.3     | quick one-liners, adb/frida orchestration, pipelines     |
| Python 3 | 3.13    | replay tooling, crypto helpers, data parsing, automation |
| Node.js  | 24.13   | HTTP clients, JSON tooling, quick API testing            |
| Bun      | 1.3.10  | fast TS/JS execution and lightweight tooling             |

### Good POC targets

- replay captured requests with modified headers or IDs
- validate auth assumptions
- dump runtime values from Frida hooks
- exercise multiple package states repeatedly
- convert captured traffic into a reusable report or HAR file

Final rule: if a claim matters, automate the proof.
