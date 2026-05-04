# Android RE Workflow

## Goals

This workflow exists to turn Android RE sessions into short, evidence-backed
loops instead of random command spraying.

Primary outputs per target:

- package identity, version, and ABI
- install and launch status
- exported components and interesting manifest flags
- likely network stack and endpoint surface
- proxy result: visible traffic / handshake failure / bypass / no traffic
- Frida result: attach works / spawn works / blocked / emulated realm needed
- anti-analysis result: root, emulator, Frida, pinning, native guards
- next best action with proof

## Core Proof Loop

Inside every phase, repeat this loop:

1. state the current hypothesis
2. run the smallest proof step that could falsify it
3. capture exact evidence
4. **write the result to the workspace and findings database immediately** —
   do not hold it in memory for later
5. either escalate, pivot, or kill the branch

Do not advance phases just because a tool succeeded. Advance because a question
was answered with evidence.

## Phase 0: Environment Validation

Run:

```bash
bash scripts/ai/android-re/re-avd.sh doctor
bash scripts/ai/android-re/re-avd.sh status
```

Confirm:

- `adb`, `emulator`, `mitmproxy`, `mitmdump`, `frida`, `jadx`, `apktool`
- local Frida server binary exists
- custom CA exists
- configured AVD exists
- `adb devices` sees the emulator
- `sys.boot_completed=1`
- `adb shell 'su 0 sh -c id'` works

If this is a new target, initialize the workspace:

```bash
bash scripts/ai/android-re/workspace-init.sh init com.example.target [/path/to/app.apk]
```

If resuming, read workspace state first:

```bash
cat ~/Documents/com.example.target/SESSIONS.md
cat ~/Documents/com.example.target/NOTES.md
cat ~/Documents/com.example.target/memory.json 2>/dev/null | jq '.knowledge[] | select(.confidence >= 0.7)'
```

If `memory.json` exists, load learned strategies and bypasses to avoid repeating
dead ends. See SESSION-MEMORY.md for the full schema and update rules.

If the workspace has a findings database, check its state:

```bash
findings-android list-vulns ~/Documents/<target> --status open
findings-android list-chains ~/Documents/<target>
```

Before every phase pivot, confirm there is no write debt: new endpoints are in
`ENDPOINTS.md`, components are in `COMPONENTS.md`, suspected or confirmed vulns
have at least a minimal `findings-android add-vuln` row, reusable lessons are in
`memory.json`, and the current step is summarized in `SESSIONS.md`.

The workspace is a git repository. Create checkpoint commits at major milestones:

```bash
git -C ~/Documents/<target> add -A
git -C ~/Documents/<target> commit -m "checkpoint: <description>"
```

If any baseline check fails, stop and use `TROUBLESHOOTING.md` before touching a
target app.

## Phase 1: Boot And Observe The Emulator

If launched via `oc*are`, the emulator is already starting in the background.
Verify readiness:

```bash
bash scripts/ai/android-re/re-avd.sh status
tail -f ~/Downloads/android-re-tools/re-avd-start.log
tail -f ~/Downloads/android-re-tools/emulator-runtime.log
```

If starting manually:

```bash
bash scripts/ai/android-re/re-avd.sh start
bash scripts/ai/android-re/re-avd.sh status
```

Healthy state means:

- AVD listed and online in `adb devices`
- boot property `sys.boot_completed=1`
- unattended root works
- proxy state is known
- tmux session `android-re` exists with `mitm`, `frida`, `logs`, `logcat`

## Phase 2: Target Intake

Before hooks or interception, identify the target precisely.

If you have an APK:

```bash
bash scripts/ai/android-re/re-static.sh prepare /path/to/app.apk
bash scripts/ai/android-re/re-static.sh hashes /path/to/app.apk
```

If the app is already installed:

```bash
adb shell pm list packages | grep example
adb shell dumpsys package com.example.target | grep versionName
adb shell dumpsys package com.example.target | rg "primaryCpuAbi|secondaryCpuAbi|nativeLibraryDir|split_config"
adb shell pm path com.example.target
adb shell getprop ro.product.cpu.abi
```

Capture:

- package name
- version
- ABI
- install path / split APK paths
- whether it likely depends on ARM translation

Record metadata in the workspace:

```bash
echo "version: <VERSION>" >> ~/Documents/com.example.target/README.md
echo "abi: <ABI>" >> ~/Documents/com.example.target/README.md
```

Pivot rule:

- if the app is ARM-only on this `x86_64` guest, treat instability as a real
  possibility and verify ABI before blaming root, proxy, or Frida.

## Phase 3: Static Triage First

Before dynamic hooking, inspect the APK output. This is where you decide which
runtime path is worth exercising.

**Write each discovery to workspace files as you find it — do not wait until
static triage is complete:**

- found an exported component → write to `COMPONENTS.md` now
- found a defense pattern → write to `ANTI-ANALYSIS.md` now
- found an endpoint or API key → write to `ENDPOINTS.md` now
- found auth/token logic → note in `NOTES.md` now

Look for:

- `AndroidManifest.xml`
- exported activities, services, receivers, providers
- deep links and intent filters
- `networkSecurityConfig` and cleartext policy
- authentication and token classes
- certificate pinning code paths
- root / emulator / Frida detection strings
- native libraries under `lib/`

Common searches:

```bash
grep -R "TrustManager\|CertificatePinner\|X509TrustManager" ~/.cache/android-re/out/<app>/jadx
grep -R "frida\|magisk\|su\|test-keys\|ro.debuggable" ~/.cache/android-re/out/<app>/jadx
grep -R "okhttp\|retrofit\|cronet\|quic" ~/.cache/android-re/out/<app>/jadx
grep -R "root\|emulator\|isDebuggerConnected\|ptrace" ~/.cache/android-re/out/<app>/jadx
```

As you discover hosts and services, record them in the findings database:

```bash
findings-android add-host ~/Documents/<target> <ip> <hostname>
findings-android add-service ~/Documents/<target> <host_id> <port> <proto> <service>
```

## Phase 3.5: Version Diff (If Two Versions Available)

If comparing an update or two builds of the same app:

```bash
bash scripts/ai/android-re/re-static.sh prepare old_version.apk
bash scripts/ai/android-re/re-static.sh prepare new_version.apk
bash scripts/ai/android-re/re-static.sh diff old_version new_version
```

Focus on:

- new or removed manifest permissions
- new or removed native libraries
- class count changes (significant growth or shrinkage)
- new endpoint strings in the updated version

Update `~/Documents/{app}/NOTES.md` with diff findings.

## Phase 3.7: Semgrep Scan

Run Semgrep against jadx output to catch vulnerability patterns that manual
grep misses. See SEMGREP-GUIDE.md for setup and custom rules.

```bash
pip install --user semgrep 2>/dev/null || true
semgrep --config auto --json ~/.cache/android-re/out/<app>/jadx/sources/ \
  -o ~/Documents/<app>/analysis/semgrep-results.json
semgrep --config auto --text ~/.cache/android-re/out/<app>/jadx/sources/
```

Write Semgrep findings to `~/Documents/<app>/analysis/semgrep-results.md`.

## Phase 3.8: Dataflow Validation

Apply the 5-step validation framework (see DATAFLOW-VALIDATION.md) to each
suspected finding from Phase 3 grep and Phase 3.7 Semgrep. For each finding:

1. **Source control:** Is the input attacker-controlled? (Intent extras from
   exported components? Deep link params? Hardcoded strings?)
2. **Sanitizer effectiveness:** Can sanitizers be bypassed? Or are there
   parameterized queries (effective)?
3. **Reachability:** Is the component exported? Permission-protected?
4. **Exploitability:** What is the full source-to-sink path? What are the
   prerequisites?
5. **Impact:** What does the attacker achieve? OWASP Mobile Top 10 category.

Classify each finding: EXPLOITABLE / FALSE POSITIVE / NEEDS TESTING

Write validated findings to `~/Documents/<app>/analysis/validated-findings.md`.

## Phase 3.9: CodeQL Deep Analysis

For high-value candidates where Semgrep cannot resolve the dataflow, run CodeQL
with targeted taint-tracking queries. See CODEQL-GUIDE.md for setup, database
creation, and custom Android queries.

```bash
# Create database from jadx output (structural analysis only)
codeql database create ~/Documents/<app>/analysis/codeql-db \
  --language=java \
  --source-root=~/.cache/android-re/out/<app>/jadx/sources/ \
  --overwrite

# Run security queries
codeql database analyze ~/Documents/<app>/analysis/codeql-db \
  codeql/java-queries:Security \
  --format=sarif-latest \
  --output=~/Documents/<app>/analysis/codeql-results.sarif
```

Save results to `~/Documents/<app>/analysis/codeql-*.sarif`.

## Phase 3.10: Native Library Fuzzing

If the APK contains native `.so` libraries (identified in Phase 3 static triage),
run AFL++ fuzzing on identified JNI entry points. See NATIVE-FUZZING.md for
corpus generation, harness construction, and crash analysis.

```bash
# Extract native libs
cp ~/.cache/android-re/out/<app>/extracted/lib/arm64-v8a/*.so \
  ~/Documents/<app>/analysis/native-libs/

# Generate format-aware seeds from binary strings
strings -n 4 ~/Documents/<app>/analysis/native-libs/*.so | \
  grep -iE '<|>|xml|json|\{|}|\[|\]|http|content:' | sort -u \
  > ~/Documents/<app>/analysis/native-strings-formats.txt
```

Save crashes to `~/Documents/<app>/analysis/fuzz-findings/`.

Static triage questions:

1. Is the app likely Java-heavy, native-heavy, or mixed?
2. Does it look like standard OkHttp/Retrofit or Cronet/native TLS?
3. Are there obvious pinning or root-check classes?
4. Do native libs suggest JNI-heavy auth or anti-analysis logic?

Pivot rule:

- if static analysis shows Cronet, BoringSSL, or native networking, assume Java
  MITM guidance may be insufficient and be ready to pivot to native analysis.

High-value static branches to rank:

1. auth, token, and session ownership paths
2. exported components, providers, receivers, and deep links
3. WebView configuration, bridges, and file/origin trust
4. local storage of tokens, credentials, keys, SQLite, prefs, or cached API data
5. native libraries that own trust, crypto, auth, or anti-analysis decisions

## Phase 4: Install, Launch, And Smoke Test

Install and launch cleanly before proxying or hooking.

```bash
adb install -r /path/to/app.apk
adb shell monkey -p com.example.target -c android.intent.category.LAUNCHER 1
adb shell pidof com.example.target
tmux capture-pane -t android-re:logcat -p -S -80
```

Then immediately use `agent-device` to navigate the initial screens:

```bash
agent-device open com.example.target --platform android
agent-device snapshot -i
agent-device screenshot --out ~/Documents/com.example.target/evidence/screenshots/01-initial-launch.png
# Navigate through the first-launch flow (onboarding, permissions, etc.)
agent-device snapshot -i
agent-device find "Skip" click || agent-device find "Next" click
agent-device screenshot --out ~/Documents/com.example.target/evidence/screenshots/02-after-onboarding.png
agent-device close
```

Capture:

- does it launch, crash, hang, or immediately complain about environment
- does `logcat` show TLS, root, tamper, debugger, or ABI failures
- which screens you reached and what permissions or onboarding it requested
- screenshot evidence of every screen state

Pivot rule:

- if the app crashes before any traffic, go to `logcat` and static code first;
  do not jump to proxy setup as if the network layer is the issue.

## Phase 5: Prepare Network Interception

Default recommendation for this emulator:

- use explicit proxy mode first
- use the custom CA under `~/Downloads/android-re-tools/custom-ca/`
- use the verified listener on `8084`
- block QUIC when testing apps that may bypass via UDP/443

Set proxy:

```bash
bash scripts/ai/android-re/re-avd.sh proxy-set 10.0.2.2:8084 --block-quic
adb shell settings get global http_proxy
```

Expected:

```text
10.0.2.2:8084
```

Read the mitm pane:

```bash
tmux capture-pane -t android-re:mitm -p -S -200
tmux capture-pane -t android-re:mitm -p -S -300 | grep -oP '(?:GET|POST|PUT|DELETE|PATCH|HEAD) https?://[^ ]+' | sort -u
tmux capture-pane -t android-re:mitm -p -S -300 | grep -iE 'authorization|bearer|x-api-key|token'
```

Interpretation:

- visible decrypted traffic -> interception works
- `Client TLS handshake failed` -> trust/pinning issue
- no traffic at all -> proxy bypass, Cronet/native path, cached connections, or
  app not actually reaching the network
- `client disconnected` -> retry, app rejection, or partial interception

Pivot rule:

- if no traffic appears, prove proxy state, mitmdump listener state, and app
  restart before concluding certificate pinning.

## Phase 5.5: Non-HTTP Protocol Handling

If static triage or runtime evidence suggests non-HTTP protocols:

Check for WebSocket:

```bash
grep -ri "websocket\|ws://\|wss://" ~/.cache/android-re/out/<app>/jadx
```

Check for gRPC/protobuf:

```bash
grep -ri "grpc\|protobuf\|ManagedChannel" ~/.cache/android-re/out/<app>/jadx
find ~/.cache/android-re/out/<app> -name "*.proto"
```

Use `frida-hook-network.js` to see all socket connections:

```bash
frida -U -n com.example.target -l scripts/ai/android-re/frida-hook-network.js -q
```

mitmproxy captures WebSocket frames automatically. For gRPC, use `grpcurl` to
probe services directly.

Pivot rule:

- if the app uses gRPC or custom protobuf, Java URL hooks will not see the
  traffic; rely on Socket.connect hooks and native analysis instead.

## Phase 6: Exercise The App Deliberately

After static triage identifies important screens or flows, use `agent-device` to
systematically trigger real behavior while proxy and logs are active.

**This is the primary dynamic analysis phase. Use `agent-device` to click
through every reachable screen, fill every form, toggle every setting, and
exercise every feature the app exposes.**

### Full UI exploration pattern

```bash
agent-device open com.example.target --platform android
agent-device snapshot -i

# Navigate bottom tabs / navigation drawer
agent-device find "Home" click
agent-device snapshot -i
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/home.png

agent-device find "Search" click
agent-device snapshot -i
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/search.png

agent-device find "Profile" click
agent-device snapshot -i
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/profile.png

agent-device find "Settings" click
agent-device snapshot -i
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/settings.png
```

### Auth flow exercise

```bash
agent-device find "Login" click
agent-device snapshot -i
agent-device fill @e5 "test@example.com"
agent-device fill @e7 "Password123!"
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/login-filled.png
agent-device find "Submit" click
agent-device snapshot -i
agent-device screenshot --out ~/Documents/{app}/evidence/screenshots/after-login.png
```

After each significant UI action, read the traffic and hook output:

```bash
tmux capture-pane -t android-re:mitm -p -S -120
tmux capture-pane -t android-re:logcat -p -S -120
```

### What to exercise systematically

Click through every reachable screen and feature in this order:

1. **Auth flows**: login, signup, password reset, OTP verification, social
   login buttons, biometric prompts
2. **Main navigation**: every tab, drawer item, and bottom nav option
3. **Data screens**: lists, detail views, search results, filters, sorting
4. **Forms**: profile edit, settings change, feedback/contact forms
5. **Media**: camera, gallery, file picker, audio recorder triggers
6. **Social**: share buttons, invite links, friend lists, messaging
7. **Payments/premium**: upgrade screens, payment forms, subscription flows
8. **Deep link entry**: navigate to any deep link paths from static triage
9. **Settings**: every toggle, every option, language change, logout
10. **Error states**: wrong password, network-off behavior, empty inputs

### Correlate each action with network

For each screen transition or button press:

1. note the action you took
2. read the mitm pane for new requests
3. read the Frida pane for hook output
4. screenshot the result
5. record in NOTES.md: "tapped X -> triggered POST /api/y -> response code"

This builds the authoritative map from user actions to backend requests.

Prioritize these deliberate proof loops:

- login / signup / password reset / refresh-token paths
- screens that consume deep links, magic links, or external intents
- flows that hit account, balance, profile, orders, or other object-owned APIs
- screens backed by WebView, file pickers, or bridge-style native interactions

## Phase 6.5: Firebase And Cloud Service Analysis

Check for cloud service integration:

```bash
find ~/.cache/android-re/out/<app> -name "google-services.json"
grep -ri "firebase\|google_app_id\|google_api_key" ~/.cache/android-re/out/<app>/apktool/res/
```

If Firebase is present, test for misconfigured rules:

```bash
# Unauthenticated read (no auth token)
http GET "https://<project-id>.firebaseio.com/.json"
# Unauthenticated write
http PUT "https://<project-id>.firebaseio.com/test-write.json" <<< '{"probe":true}'
```

Check for exposed API keys in the manifest or resources. Test whether keys are
restricted to specific APIs, referrers, or app signatures.

Pivot rule:

- misconfigured Firebase with open read/write is a direct finding
- unrestricted API keys that an attacker could abuse are a finding
- cloud service findings should go into `~/Documents/{app}/FINDINGS.md` under M8

## Phase 7: Prepare Frida

Use the system Frida `17.5.1` toolchain only.

Before inventing new hooks, try the local hook library in
`scripts/ai/android-re/` first. It gives fast proof for common build-field,
filesystem, shared-preferences, URL, and certificate-pinning questions.

```bash
bash scripts/ai/android-re/re-avd.sh frida-start
frida --version
frida-ps -U | head -20
adb shell "su 0 sh -c 'ps -A | grep frida'"
```

Attach modes:

```bash
# Attach to a running process
frida -U -n com.example.target

# One-shot inline probe
frida -U -n com.example.target -q -e 'console.log("attached")'

# Spawn mode for early bypasses
frida -U -f com.example.target -l hook.js

# Emulated realm for translated code paths
frida -U -n com.example.target --realm=emulated
```

Use tmux for long-running hooks:

```bash
tmux send-keys -t android-re:frida C-c
tmux send-keys -t android-re:frida "frida -U -n com.example.target" Enter
sleep 3
tmux capture-pane -t android-re:frida -p -S -60
```

Pivot rule:

- if attach fails, try PID, spawn, then `--realm=emulated` before assuming Frida
  detection.

## Phase 8: Anti-Analysis And Hooking

Only move here after static analysis or runtime evidence points to a concrete
guard worth bypassing.

Prefer this order:

1. reusable local hook library
2. target-specific inline or file-backed Frida hooks
3. external research on official docs, GitHub, CVEs, advisories, or known bypass patterns
4. subagents for deeper static/native/protocol analysis when a branch becomes too
   deep for the main session

### Common Java targets

- `okhttp3.CertificatePinner`
- custom `TrustManager` implementations
- root-check helper classes
- `android.os.Build`
- `java.io.File.exists`
- package and process checks for Magisk/Frida

### Common anti-analysis patterns

- root file checks: `su`, `magisk`, `busybox`, writable system paths
- emulator checks: `Build.*`, `ro.kernel.qemu`, qemu file paths, sensor absence
- Frida checks: process names, open ports, loaded classes, timing anomalies
- pinning: `CertificatePinner`, custom trust managers, native SSL verification
- bypass paths: QUIC, Cronet, direct sockets, native TLS

### Quick recon hooks

```bash
# What Build fields does the app see?
frida -U -n com.example.target -q -e '
Java.perform(function(){
  var B = Java.use("android.os.Build");
  console.log("MODEL=" + B.MODEL.value + " HARDWARE=" + B.HARDWARE.value + " BRAND=" + B.BRAND.value);
});
'

# Log Java URL creation
frida -U -n com.example.target -q -e '
Java.perform(function(){
  var URL = Java.use("java.net.URL");
  URL.$init.overload("java.lang.String").implementation = function(u){
    console.log("[URL] " + u);
    return this.$init(u);
  };
});
'
```

### Native pivot conditions

Move to native hooks or binary analysis when:

- Java hooks only hit wrappers
- static analysis shows JNI-heavy auth or pinning
- the app uses Cronet or native TLS
- pinning appears to live in native libs
- Java-level bypasses do not change runtime behavior

### Bypass discipline

- bypass only the guard you can name and prove
- treat root, emulator, Frida, and pinning work as enablers for higher-value
  proof loops, not as the final result
- after each bypass attempt, immediately re-run the blocked action and check
  whether it unlocked traffic, code paths, secrets, or exploitability
- if a bypass changes nothing observable, stop repeating it and revisit the
  hypothesis

## Phase 8.5: SDK And Dependency Triage

Identify third-party SDKs from static analysis:

```bash
# Common SDK package prefixes
grep -r "com.google.firebase\|com.facebook\|com.mixpanel\|com.amplitude\|io.fabric\|com.crashlytics\|com.appsflyer\|com.adjust" ~/.cache/android-re/out/<app>/jadx/sources/ | cut -d: -f1 | sort -u
```

For each identified SDK:

1. record name, version (if determinable), and purpose
2. search for known CVEs: `https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=<sdk-name>`
3. check whether the SDK handles auth, analytics, ads, payment, or push
4. SDKs handling auth or payment are higher priority for vulnerability research

Focus on SDKs that:

- handle authentication or session management
- process payment or financial data
- collect analytics or PII
- implement push notification or messaging
- provide ad serving or tracking

## Phase 9: Prove Findings With POC Scripts

When you find interesting behavior, write a script to prove it. Do not stop at
describing the finding. Follow the exploit development methodology in
EXPLOIT-METHODOLOGY.md: working code only, complete and executable, documented,
with a quality checklist.

Before writing a PoC, add the finding to the exploitation queue in
`exploitation_queue.json` with status `in_progress`. After proving,
update to `exploited`. See EXPLOITATION-QUEUE.md.

Only write PoCs for findings validated as EXPLOITABLE or NEEDS TESTING in
Phase 3.8. FALSE POSITIVE findings are documented but not proven.

Available runtimes:

- Bash
- Python 3.13
- Node.js 24.13
- Bun 1.3.10
- Frida JS

Typical POC patterns:

```bash
# Replay a captured request
curl -s "https://api.example.com/v1/users/me" | jq .

# Iterate an IDOR candidate
for i in $(seq 1 10); do
  curl -s -H "Authorization: Bearer $TOKEN" "https://api.example.com/v1/users/$i" | jq '.email'
done

# Use a Frida script file for repeatable runtime capture
frida -U -n com.example.target -l /tmp/hook.js -q
```

The final deliverable should be operator-usable evidence, not just notes.

Follow the proof-of-exploitation levels and bypass exhaustion protocol in
EXPLOIT-VERIFICATION.md. You MUST reach Level 3 (confirmed exploitation with
data/access) to classify a finding as EXPLOITED. Attempt minimum 5-6 distinct
bypass techniques before classifying as FALSE POSITIVE.

## Phase 9.5: Content Provider SQL Injection

For each exported content provider identified in static analysis:

```bash
# Basic query (already in component testing)
adb shell content query --uri content://com.example.target.provider/data

# Test projection injection
adb shell content query --uri content://com.example.target.provider/data --projection "* FROM sqlite_master--"

# Test selection injection
adb shell content query --uri content://com.example.target.provider/data --where "1=1 OR 1=1"

# Test withSQLite-style payloads
adb shell content query --uri content://com.example.target.provider/data --where "' OR '1'='1"
```

Use `frida-hook-intent.js` to trace provider access and see what queries the app
itself makes:

```bash
frida -U -n com.example.target -l scripts/ai/android-re/frida-hook-intent.js -q
```

## Phase 10: Confidence And Chaining Review

Before ending the session, classify each branch. Where dataflow validation
was performed, use the richer verdict from DATAFLOW-VALIDATION.md:

- `proven` (dataflow verdict: EXPLOITABLE, confidence ≥ 0.8)
- `likely` (dataflow verdict: EXPLOITABLE or NEEDS TESTING, confidence 0.5-0.8)
- `suspected` (dataflow verdict: NEEDS TESTING, confidence < 0.5)
- `blocked` (promising path halted by a proven technical blocker)
- `false_positive` (dataflow verdict: FALSE POSITIVE — document but do not PoC)

Apply the adversarial priority order from FINDINGS-PRIORITIZATION.md:
secrets first, then input validation, then auth/authz, then crypto, then
configuration.

Then ask:

- what is the strongest attacker-usable primitive I proved?
- what trust boundary did it cross?
- what does it unlock next?
- what is the next best operator action if the session continues?

Apply the Critical Decision Test from EXPLOIT-VERIFICATION.md for each finding:
is the prevention a security feature (FALSE POSITIVE) or an external constraint
like emulator limitation (POTENTIAL)?

For every confirmed finding (proven or likely confidence), generate detection
content per DETECTION-PAIRING.md: at minimum one YARA rule, Sigma rule,
network IOC, or SIEM query. Store in the findings database detection fields.

## Phase 10.5: Traffic Correlation

Correlate Frida hooks with mitmproxy captures to build a complete request map:

1. start `frida-hook-network.js` and `frida-hook-url-log.js` together
2. use `agent-device` to exercise specific UI flows one action at a time
3. after each `agent-device` action (click, fill, find), immediately read
   both the mitm pane and Frida pane
4. match Frida connection logs with mitmproxy request logs in the same window
5. for each UI action, identify the exact API calls it generates
6. record the mapping: UI action -> endpoint -> request/response -> purpose

This builds the authoritative map from user actions to backend requests.

If you have not yet done full UI exploration, go back to Phase 6 and use
`agent-device` to systematically click through every remaining screen.

## Phase 11: Backup Extraction Testing

Check whether the app allows backup extraction:

```bash
grep -i "allowBackup\|fullBackupContent" ~/.cache/android-re/out/<app>/apktool/AndroidManifest.xml
```

If `allowBackup=true` or unset (default is true for API < 31):

```bash
adb backup -f ~/Documents/{app}/evidence/target.ab com.example.target
```

Extract and analyze:

```bash
dd if=~/Documents/{app}/evidence/target.ab bs=1 skip=24 | python3 -c "import zlib,sys; sys.stdout.buffer.write(zlib.decompress(sys.stdin.buffer.read()))" | tar xf - -C ~/Documents/{app}/evidence/backup/
```

Look for: tokens, credentials, cached API responses, SQLite databases, shared prefs.

If `allowBackup=false`, use root:

```bash
adb shell "su 0 tar -cf - /data/data/com.example.target" | tar xf - -C ~/Documents/{app}/evidence/root-extract/
```

## Phase 12: Magisk/Zygisk Advanced Bypass

When standard Java hooks and Frida bypasses fail because the app uses native
detection or checks Magisk-specific artifacts:

1. Add target to Magisk DenyList: `adb shell "su 0 magisk --denylist add com.example.target"`
2. Enable Zygisk in Magisk settings
3. Install Shamiko module for comprehensive hiding (hides Magisk binaries, mount
   points, and Zygisk from the target process)
4. After configuration, reboot the emulator and re-test

Use this path only when:

- Java-layer `File.exists` hooks fire but the app still detects root
- The app probes `/proc/self/mounts` or checks for Magisk-specific paths natively
- Standard Frida hooks are loaded but anti-analysis behavior persists

## Phase 13: Encrypted/Packed DEX Handling

If `jadx` output is suspiciously small or shows a single wrapper class:

1. Check for dynamic class loading:

```bash
grep -r "DexClassLoader\|InMemoryDexClassLoader\|PathClassLoader" ~/.cache/android-re/out/<app>/jadx
```

1. Use `binwalk` to find embedded DEX:

```bash
binwalk -e path/to/app.apk
```

1. Hook class loaders at runtime to dump unpacked DEX:

```bash
frida -U -f com.example.target -q -e '
Java.perform(function(){
  var DexClassLoader = Java.use("dalvik.system.DexClassLoader");
  DexClassLoader.$init.implementation = function(dexPath,optimizedDir,libPath,parent){
    console.log("[unpack] dexPath=" + dexPath);
    return this.$init(dexPath,optimizedDir,libPath,parent);
  };
  var InMemory = Java.use("dalvik.system.InMemoryDexClassLoader");
  InMemory.$init.overload("[Ljava.nio.ByteBuffer;","java.lang.ClassLoader").implementation = function(buffers,parent){
    console.log("[unpack] InMemoryDexClassLoader bufferCount=" + buffers.length);
    return this.$init(buffers,parent);
  };
});
'
```

1. Save unpacked DEX to `~/Documents/{app}/analysis/unpacked/`
1. Re-run `jadx` on the unpacked DEX for full analysis
