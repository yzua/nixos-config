# Native query interfaces

## Rizin: metadata before analysis

Reviewed **0.8.2** [rz-bin source/help](https://github.com/rizinorg/rizin/blob/v0.8.2/librz/main/rz-bin.c).
Use detected version, `rz-bin -h`, `rizin -h` and command-specific `?` help before
queries. Pin rz-pipe bindings separately and check against installed Rizin.
Primary [scripting guide](https://book.rizin.re/src/scripting/intro.html) and
[rz-pipe repository](https://github.com/rizinorg/rz-pipe) explain pipe lifecycle;
read the matching binding revision before using its open/cmd/cmdj/quit methods.
No persistent query wrapper is supplied here.

```bash
# BINARY is an approved immutable input; outputs stay private pending release.
rz-bin -j -I "$BINARY" > "$PRIVATE_META"
rz-bin -j -s -n "$SYMBOL" "$BINARY" > "$PRIVATE_SYMBOL"
```

Expected: JSON binary metadata, then selected symbol evidence; check exits and
schema rather than assuming every format/plugin returns the same fields.
0.8.2 supports `-i` imports, `-s` symbols, `-S` sections, `-n` name selection,
`-@` address selection and `-B` base override. Choose one category/address/name.
Avoid `-g` whole metadata and unbounded raw string dumps. Save outputs privately,
select at most 25 records/16 KiB after format validation and release review.
A quick parser query has a 30-second external deadline; deep analysis gets a
separately recorded finite budget. JSON support is command-specific, not universal.

Use read-only input modes and reviewed configuration/plugins. Rizin startup can
load ambient plugins/config; inspect and constrain that surface within the
approved environment. `-Q` loads a library with dlopen: it is sample execution,
not harmless metadata. PDB/debuginfod download options send traffic and are not part of offline
inspection. Block unapproved execution/download/plugin paths rather than trusting
a filename extension. Fat Mach-O/sub-binaries require explicit architecture.

## Ghidra: batch engine, not an assumed query service

Use the installed distribution's `support/analyzeHeadlessREADME.html` (or the
README shipped by that release), headless usage output and matching Java API docs.
Reviewed source baseline **11.4.2** primary references:
[headless manual](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_11.4.2_build/Ghidra/RuntimeScripts/Common/support/analyzeHeadlessREADME.md),
[GhidraScript](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_11.4.2_build/Ghidra/Features/Base/src/main/java/ghidra/app/script/GhidraScript.java),
[FunctionManager](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_11.4.2_build/Ghidra/Framework/SoftwareModeling/src/main/java/ghidra/program/model/listing/FunctionManager.java),
[ReferenceManager](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_11.4.2_build/Ghidra/Framework/SoftwareModeling/src/main/java/ghidra/program/model/symbol/ReferenceManager.java),
[decompiler](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_11.4.2_build/Ghidra/Features/Decompiler/src/main/java/ghidra/app/decompiler/DecompInterface.java).
This anchors API shapes, not a toolchain pin. Record installed Ghidra/JDK version
and local matching API/help revision before code. A baseline method absent in
the installed release is blocked.

The documented batch shape is:

```text
analyzeHeadless <owned-project-parent> <project-name> -import <approved-binary> \
  -analysisTimeoutPerFile 60 -max-cpu 1
```

This example's 60-second per-file analysis budget does not bound import/scripts
or the whole process; apply an external finite run budget. Read matching help for
processor/loader, script path,
`-postScript`/`-process`, or read-only project options. No `query.py`/export script
is bundled here. Write bounded task-specific code when needed, review installed
APIs and test it on owned inputs under the shared capability policy. Do not
invoke invented script names. Import/analysis writes a project; one writer
owns it. Create a fresh project or verify existing binary hash/base/analysis state
before reuse. GUI is an optional human companion, not the headless API.

For task-specific Java/Python export code, select one function entry address via
`currentProgram.getFunctionManager().getFunctionAt(address)`, then request bounded
references with the reference manager. Decompiler API lifecycle: create/open the
program, decompile the selected function with a finite timeout/monitor, check the
result's completion/error, export selected approved text, and dispose the interface.
Verify exact method signatures against the installed API and scripting language
(Jython, PyGhidra or Java as actually provisioned). Whole-program C export is not
a bounded per-function query. Save query code/revision and output hashes.

## Address and failure contract

Record binary hash/build ID, format, architecture/ABI/endianness, loader and base,
address space, selected function/symbol, and file versus virtual/runtime offsets.
PIE/ASLR addresses need module-base conversion before instrumentation. A symbol
name can be missing/duplicated/demangled; preserve original identity too.

Analysis timeouts, unsupported loaders, skipped functions, failed decompilation,
unresolved indirect calls and unknown types are `partial`/`blocked`, not clean
absence. Headless process success alone does not prove all analyzers completed.
Keep logs/status and tested coverage. Unknown executable samples require an
approved whole-process lab boundary before dynamic analysis.

Optional pyghidra-mcp/JADX/Ghidra bridges remain unfinished/disabled. If later
enabled, check host/plugin/transport compatibility, test bounded paths and
distinguish read-only versus mutation methods: a headless backend differs from
server-launched GUI, an HTTP-only CLI differs from stdio MCP,
and a new server cannot attach to an arbitrary personal GUI. No silent bridge
installation follows an awkward query. Close owned pipes/decompiler/project work
and retain partial exports; never start a second writer to solve a timeout.
