# Bounded queries, replay and test code

Use installed help for the provisioned version of rg/jq/curl/Python/Node/test
runner. This guide supplies limits and selection rules, not new wrapper flags.
Primary references: [ripgrep GUIDE](https://github.com/BurntSushi/ripgrep/blob/14.1.1/GUIDE.md),
[jq 1.7 manual](https://jqlang.org/manual/v1.7/),
[curl manual](https://curl.se/docs/manpage.html),
[Python library docs](https://docs.python.org/3/library/),
[Node API versions](https://nodejs.org/docs/).
Select Python/Node documentation matching the detected minor version.

## Selection before output

Default reporting budget: 25 summary records, 16 KiB model-visible output,
30-second query deadline. These are local query budgets, not invented engine
options. Set separate finite import/analysis/capture budgets before bulk work.
Save bulk output and diagnostics to separate private files; check exit status,
size and release approval before emitting selected fields. Truncating stdout
with `head` neither proves completion nor stops background children safely.

A smallest offline query, on an approved text fixture:

```bash
# INPUT_TEXT is one approved file, NEEDLE is a literal chosen term.
rg -n -F -m 25 -- "$NEEDLE" "$INPUT_TEXT"
```

Exit 0 means matches, 1 no matches, 2 error. `-m` is per-file; applying it to a
whole tree can exceed the total budget. First select a short file list, then
query individual files. Match lines can be huge; review file sizes and bound
line bytes separately. Binary/encoded data needs a decoder with explicit size
and format handling; do not infer absence from text search.

For an approved JSON fixture containing a known array:

```bash
jq '[.operations[:25][] | {id, method, status}]' "$FIXTURE_JSON"
```

This selects known fields; it is not generic redaction. Reject schema mismatch
or parse error, record omitted count, and page explicitly rather than repeatedly
raising limits. An upstream filter often controls visibility, not network scope.

## Replay is traffic

Authorize destination/account/method/body, redirect policy, total attempts,
rate and timeout before a request. Check transport status separately from HTTP
status; a valid 4xx/5xx is evidence, not always a transport failure. curl does
not follow redirects unless requested; validate each destination before enabling
redirects. Keep TLS verification enabled. Private headers/cookies and bodies
belong in protected files or approved secret injection, not inline arguments.

For a credential-free owned loopback mock, with approved response content:

```bash
curl --connect-timeout 3 --max-time 10 --max-filesize 16384 \
  --output "$PRIVATE_BODY" --dump-header "$PRIVATE_HEADERS" \
  --write-out '%{http_code}\n' "$MOCK_URL"
```

Record curl exit and HTTP status. Confirm `--max-filesize` behavior for the
installed version and streaming/unknown-length responses; impose storage limits
outside curl where needed. Do not use insecure TLS or automatic retries to mask
an error. Preserve exact response bytes privately, decode copies with stated
encoding, then release approved fixtures only.

## Test code, not assumed scripts

Task-specific Python/Node code must name inputs, enforce deadlines/record and
byte limits, separate diagnostics, handle corrupt/missing data, and guarantee
owned-resource cleanup in `finally`. Review dependency/import side effects.
Run only already provisioned runtimes/libraries; no package-manager bootstrap.
Use deterministic offline positive/negative fixtures before live tests.

Retries are finite and allowed only after checking whether a previous mutation
completed. Non-idempotent submit/payment/delete/replay actions require explicit
reconciliation, not blind retry. Test cancellation, partial data, wrong identity,
unsupported versions, timeouts and malformed input. Passing a mock contract
proves that contract under those fixtures, not complete upstream equivalence.
