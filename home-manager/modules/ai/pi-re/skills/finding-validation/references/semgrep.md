# Local Semgrep and controlled validation

## Version and coverage

Reviewed CLI source baseline **1.136.0**:
[scan options](https://github.com/semgrep/semgrep/blob/v1.136.0/cli/src/semgrep/commands/scan.py).
This anchors example flags/telemetry environment names, not a runtime pin.
Use detected `semgrep --version` and `semgrep scan --help`. Primary
[CLI reference](https://semgrep.dev/docs/cli-reference),
[rule syntax](https://semgrep.dev/docs/writing-rules/rule-syntax), and
[Semgrep source releases](https://github.com/semgrep/semgrep/releases)
are references; select source/help matching the provisioned release before
commands/rule features. No current package version or proprietary engine is
assumed. Document engine/edition, language/parser and rule revision/hash.

Local source/decompiled fixtures are not equivalent to complete original source.
Parsing errors, excluded/generated files, unsupported languages, file size limits,
per-file timeouts and cross-file/dataflow engine limits affect coverage. Community
and proprietary/managed modes differ in capabilities, login and licensing.
Use local reviewed rules; cloud/registry rules/login/uploads are separate gates.

## Small local scan

On one approved source fixture with a reviewed local rule, after matching help
confirms these flags:

```bash
SEMGREP_SEND_METRICS=off SEMGREP_ENABLE_VERSION_CHECK=0 \
  semgrep scan --config "$LOCAL_RULE" --json --metrics off \
  --timeout 5 --max-target-bytes 100000 --jobs 1 "$SOURCE" \
  > "$PRIVATE_RESULT"
```

Expected: JSON candidate locations, rule IDs and diagnostics, plus checked exit.
These common scan controls must be confirmed against installed help/source.
Apply an external finite overall deadline and private output/storage budget;
per-file timeout is not total scan timeout. Validate JSON and record scanned versus
skipped/error files; a zero match count with incomplete parsing is not clean.
Review environment telemetry/version policy before execution. Do not use auto
configuration, remote registry rules, autofix or target build hooks in this branch.
CLI metrics-off alone is not a whole-process no-network guarantee.

Semgrep tests use matching `semgrep test --help` and approved positive/negative
fixtures for the local rule; this resource does not bundle a test runner or rules.
If Semgrep is unavailable/incompatible, proceed with an authorized manual
falsifiable fixture experiment or report blocked candidate generation. Do not
install it or silently replace it with a remote scanner.

## Falsifiable experiment

Define before execution: claim, affected trust boundary, target/build/account,
preconditions, minimal action, expected positive/negative outcomes, control,
finite attempts/rate/time/storage and stop conditions. Start offline/on a mock
where it answers the claim. Live confirmation needs its own authorization.

Retain private input bytes, test code/rule hashes, exact commands, expected versus
observed behavior and error/partial data. A positive control proves the test can
observe the behavior; a negative control discriminates the proposed cause from
normal failure. A rejected claim is local to tested prerequisites/coverage.
Report candidate, confirmed, rejected or blocked with evidence, not a score alone.

## Optional assessment tools

ZAP passive observation differs from crawl/active scan; Nuclei template side
effects/OAST/redirects need pinned template review and aggregate budgets. CodeQL
needs real extraction/database/query coverage and licensing. MobSF needs a
compatible private disposable lab/API with a bounded experiment. AFL++ needs an ABI-correct offline harness,
coverage and crash reproduction/minimization. Burp editions/bridges and cloud
services have separate licenses/exposure. All remain disabled initially; use
only a later available compatible pack with bounded fixture evidence and scope.
No generic scan permission or error hint authorizes enabling these tools.
