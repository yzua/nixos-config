# Adapter tests and Caddy edge

## Choose the seam

A capture prototype records observed bytes. A compatible client implements
selected operations/state. A semantic adapter translates behavior between
contracts. A gateway provides a deployable HTTP edge; it is not the traffic
capture tool. Put semantic/state translation in typed tested application code,
not incidental proxy header rewrites. Choose only provisioned Python/Node or the
project's approved runtime/test runner; read installed help/types matching version.
No generated adapter/build/deploy script is assumed to exist.

Record approved fixture hashes, operation pre/postconditions, required state,
unknown fields, errors/status, retry/idempotency, auth boundaries, cancellation,
streaming/backpressure/WebSocket behavior and unsupported branches. Test positive,
negative/malformed, timeout, partial and ordering cases against an owned mock
before any live compatibility claim. Exact observed bytes and inferred semantic
schemas remain distinct. Never embed captured tokens or provider credentials.

## Caddy interface

Reviewed baseline **2.10.2**
[command source](https://github.com/caddyserver/caddy/blob/v2.10.2/cmd/commandfuncs.go).
Use detected `caddy version`, `caddy help adapt`, `caddy help validate`, and
matching source/module inventory before configuration.
Primary [CLI](https://caddyserver.com/docs/command-line),
[reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[admin API](https://caddyserver.com/docs/api), and
[JSON config](https://caddyserver.com/docs/json/) are context; online behavior
can differ from installed Caddy/plugins. A missing module blocks that branch;
never run upgrade/add-package commands to repair it silently.

For a reviewed local Caddyfile with no secret/network provisioners:

```bash
caddy adapt --config "$CADDYFILE" --adapter caddyfile > "$PRIVATE_JSON"
caddy validate --config "$CADDYFILE" --adapter caddyfile
```

Expected: adapted JSON + separate warnings, then checked validation success/error.
`adapt` translates syntax; `validate` loads/provisions modules for stronger checks
without serving. Module provisioning can read files or have side effects; inspect
configuration/modules first and use approved local state. Neither command proves
upstream reachability, correct Host/TLS handling or safe deployment.
Keep generated JSON/diagnostics private; configuration can contain credentials.
Use finite external deadlines and byte limits before model output.

## Version and mode caveats

- Caddyfile versus native JSON: adapter translation and provisioning are different
  stages; record warnings and adapted config hash. Modules/plugins are versioned
  capabilities, not assumed by a generic Caddy executable.
- Upstream Host versus TLS SNI: test against matching version and actual upstream.
  Caddy 2.11+ HTTPS Host behavior differs from older examples; confirm release
  source rather than copying `header_up Host` blindly. Never disable TLS
  verification as a compatibility fix. Preserve intended origin/auth boundaries.
- Streaming/WebSockets: test upgrade, chunking, cancellation, buffering,
  backpressure and timeout behavior; a simple JSON roundtrip is insufficient.
- Automatic HTTPS may contact ACME and write key/certificate state when serving;
  local validation and production serving are separate permissions. Do not expose
  admin/listener ports, trust an internal CA or acquire certificates implicitly.
- Foreground `run` versus background `start`, `reload`/admin `POST /load`, and
  `stop`/admin `POST /stop` have different lifecycle/mutation semantics.
  Read matching help/API first. Bind explicit owned admin/listener endpoints and
  state before any run; default global endpoints are not safe ownership evidence.
- Deployment/reload is a separate reviewed action requiring target/service owner,
  credentials policy, readiness checks, rollback and finite activation budget.
  A passing build or config check does not authorize privileged activation.

## Recovery and handoff

Stop only verified owned local mocks/edge processes. Inspect uncertain outcomes
before retrying stateful operations/reloads. Record produced binary/config/test
hashes, supported behavior, fixture provenance, errors/limitations and residual
state. Provide reproducible tests and a reviewed deployment plan, not an invented
`pi-re deploy` command. nginx/Envoy/cloud edges are not provisioned by this guide;
an available alternative needs its own scope, API review and bounded tests, not
an automatic stack switch if Caddy lacks a feature.
