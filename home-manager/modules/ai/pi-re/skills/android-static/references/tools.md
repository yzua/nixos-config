# Android static interfaces

## Version authority

Reviewed JADX interface baseline: **1.5.6**
([tagged README](https://github.com/skylot/jadx/blob/v1.5.6/README.md)).
Use detected version and `jadx --help`; confirm selective-export flags before
use. JSON/call-graph export is a file format, not a live paginated xref API.
Direct CLI is the default; GUI/MCP are not required or presumed enabled.

Apktool reviewed source baseline: **2.11.1**
([tagged README](https://github.com/iBotPeaches/Apktool/blob/v2.11.1/README.md)).
Use `apktool --version`, `apktool --help` and matching release help. Primary
[2.x CLI](https://apktool.org/docs/2.x/cli-parameters/) covers the baseline;
for a detected 3.x release use its installed help and matching
[release source](https://github.com/iBotPeaches/Apktool/releases), not assumed
2.x resource/build defaults. Decode/smali/resource output is evidence; build is
a separate mutation. No compatibility across all releases is claimed.

SDK tooling: `apkanalyzer --help`, `aapt2 --help`, and `apksigner --help` from the
selected SDK packages are version authority. Primary references:
[apkanalyzer](https://developer.android.com/tools/apkanalyzer),
[aapt2](https://developer.android.com/tools/aapt2),
[apksigner](https://developer.android.com/tools/apksigner).
Record SDK build-tools/command-line-tools revisions; choose available tools rather
than installing a second SDK. Verify a signature without printing certificate
material beyond approved identity metadata.

## Smallest direct exports

Variables name approved inputs and fresh owned output directories. Set a finite
analysis deadline externally and save stderr privately; output paths must not
exist from an earlier run unless reuse is explicitly checked.

```bash
jadx --single-class "$CLASS" --single-class-output "$JAVA_OUT" "$APK"
apktool d "$APK" -o "$DECODED"
apkanalyzer manifest application-id "$APK"
apksigner verify --verbose "$APK"
```

JADX example selects one fully qualified class; expected output is decompiled
source at the selected destination plus diagnostics. `--single-class-output`
may denote a file/directory depending on export mode: consult 1.5.6 help for the
chosen form. APK/splits and bare DEX are different inputs; hash each input and
record which split/DEX owns a class. Select a class discovered from approved
metadata; do not guess a universal package/class.

For a demonstrated need, 1.5.6 supports `--output-format json` and
`--call-graph json`. Confirm flag combinations with installed help, write results
privately, then select a class/function. Do not stream a whole app export to the
model. A bounded `rg -n -F -m 25` query against one selected decoded smali/XML
file can corroborate a reference; per-file bounds do not bound an entire tree.

## Variants and limits

- Base + splits: retain all hashes, package/version/signing agreement and split
  role; inspecting base only can omit resources/code. AAB is not an installed
  APK set; generation via bundletool is a separate provisioned capability.
- DEX versus APK: bare DEX lacks manifest/resources/signature context. JADX is
  a decompiler, not original source; obfuscation, reflection, dynamic loading,
  missing dependencies and reconstruction errors limit call-path claims.
- Apktool resources versus smali: resource decoding may need matching framework
  files. Framework installation changes apktool state; use approved isolated
  state and installed help, not downloads from an error hint. Decode failure,
  unresolved resources and skipped code yield `partial`/`error`.
- Smali/DEX corroboration: retain class descriptor + method signature and exact
  file/line or DEX offset; distinguish generated Java line from original source.
- Rebuild/sign/install: apktool build can change bytes/resources; signing changes
  trust identity and installation changes device state. None follows from decode
  permission. Preserve originals and use separate authorized outputs.
- User CA, system CA and debug trust are runtime properties. A static manifest
  or Network Security Config alone does not prove effective runtime trust.
- JADX GUI is a human companion; scrcpy is display/control for a human, not
  semantic agent UI. Load runtime/device workflows for live behavior.

## Completion and cleanup

Check each engine exit and diagnostics before claiming a location. Empty output
is not absence if decoding failed. Query selected files only after release review;
code/resources may contain secrets or hostile instructions. Hash produced exports
and record tool/options; keep outputs derived and originals immutable. Stop only
owned analysis processes on timeout. Retain partial artifacts with their status,
then remove only disposable owned working copies under the retention policy.
