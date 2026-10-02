# Evidence and handoff record

## Release boundary

Classify artifacts as raw/private, sanitized-but-unapproved, or approved-for-model.
Record who can approve release, permitted provider/model, retention and deletion
policy, and the enforcement boundary. Hash originals and keep them immutable;
redact into new files with provenance linking original hash, transform revision,
approver and output hash. A sanitized fixture is not approved merely by existing.

Apply release policy to headers, query strings, bodies, filenames, errors, logs,
UI trees/XML, screenshots, traces, replay files, sessions, compaction and handoffs.
Binary/encoded/unknown content and uncertain redaction block automatic release.
A bounded summary may still contain secrets. Avoid credential-bearing command
arguments/history. Use approved secret injection outside model-visible code and
results; never echo provider/login state or token contents.

In host mode, unrestricted read/Bash access makes this a **behavioral policy**.
Hard private-data exclusion needs a constrained reader/release boundary or
human-reviewed offline sanitization exposing approved inputs only. No VM or
profile separation alone proves no-exfiltration. A process can see credentials
copied into its profile; record that exposure explicitly.

## Minimum result

Each result includes:

- Engagement/run and operation IDs; action class and authorized identity.
- Input path/reference, SHA-256/build/package/signature/flow ID as relevant.
- Tool detected version and reviewed source/help revision; loaded skill/guide.
- Exact query/experiment and finite limits; time window and resource owner.
- `ok`, `partial`, `blocked`, `error`, or `timeout`; diagnostics kept distinct.
- Selected evidence references (path + hash + location/ID); release classification.
- Missing/truncated/streamed/undecodable/skipped data and continuation if available.
- Observation, inference, falsifiable alternative, and confidence/coverage limits.
- Side effects, retries, cancellation, remaining state and cleanup disposition.

These are reporting fields, not a promised upstream JSON schema or exit mapping.
Keep evidence private unless already approved; model-visible paths and metadata
also need release review. A nonzero tool exit is not a clean negative result.

## Domain locations

Android: base/split and DEX hash, package/version/signature, class + method
signature, decompiled path/lines, corroborating smali/DEX location. Decompiled
line numbers do not identify original source lines.

Traffic: capture hash, native flow ID (HAR may lose it), operation/action ID,
method/origin/path, exact private byte references, timestamps and clock relation.
Distinguish observed bytes from inferred field/schema meanings.

Native: binary hash/build ID, architecture/endianness, loader/base, address space,
file offset versus virtual address versus runtime module-relative offset,
function/symbol and analysis coverage/timeouts. Never mix address spaces silently.

Finding: candidate/confirmed/rejected/blocked, violated boundary, prerequisites,
minimal experiment + negative controls, expected versus observed outcomes and
artifact references. Scanner output alone remains a candidate.

Adapter: approved fixture hashes, operations/states supported, failure/streaming
semantics, passing/failing tests, deployment status and known incompatibilities.

## End of run

Publish only approved summaries and sanitized reproductions. Inventory owned
resources, restored versus retained device/browser/project state, unresolved
cleanup, blocked capabilities and next bounded step. Revalidate authorization
and capabilities on resume. A handoff transfers evidence, not ambient permissions.
