# Traffic interfaces and mode selection

## Version authority

Reviewed mitmproxy baseline **12.2.3**:
[CLI source](https://github.com/mitmproxy/mitmproxy/blob/v12.2.3/mitmproxy/tools/cmdline.py),
[FlowReader](https://github.com/mitmproxy/mitmproxy/blob/v12.2.3/mitmproxy/io/io.py),
[HAR exporter](https://github.com/mitmproxy/mitmproxy/blob/v12.2.3/mitmproxy/addons/savehar.py),
[HTTP objects](https://github.com/mitmproxy/mitmproxy/blob/v12.2.3/mitmproxy/http.py),
[addon events](https://docs.mitmproxy.org/stable/api/events.html),
[modes](https://docs.mitmproxy.org/stable/concepts/modes/).
Use `mitmdump --version`, `--help`, `--options` and matching source for the
installed release. Stable documentation may be newer than the provisioned version.
No custom `pi-re flow` interface exists by virtue of this guide. Direct Python
calls below are task-code examples, not shipped scripts; ordinary in-scope work
may write/run bounded readers with installed dependencies.

## Owned Android forward capture

For the requested rooted-emulator capture and system-CA/proxy setup, read
[coordinated lab](../../android-runtime/references/lab.md). `pi-re lab start`
provides dedicated loopback forward capture according to the
[contract's default/narrow-mode rule](../../../contract.md#open-box-autonomy),
verified upstream TLS and a private persistent CA. `lab stop` restores only owned
guest proxy changes. The fixture check verifies decrypted HTTPS and narrow-mode
CONNECT denial; it is not a generic replay/flow-reader interface. Other capture
modes below need their own routing/readiness and scope checks.

## Pure offline reading

Prefer `mitmproxy.io.FlowReader` over dispatching captures through mitmdump addons.
The following task-code shape selects at most 25 HTTP flow identity/method/status
records from at most 100 native flows, under an external finite process deadline.
Use only approved inputs/metadata; identifiers can still be sensitive.

```python
from mitmproxy import http, io
from mitmproxy.exceptions import FlowReadException

count = scanned = 0
try:
    with open(CAPTURE, "rb") as stream:
        for flow in io.FlowReader(stream).stream():
            scanned += 1
            if isinstance(flow, http.HTTPFlow):
                print(flow.id, flow.request.method,
                      flow.response.status_code if flow.response else None)
                count += 1
            if count >= 25 or scanned >= 100:
                break
except (OSError, FlowReadException) as error:
    # Save approved diagnostic privately and report error/partial, not empty.
    raise
```

Record scanned/count and whether iteration exhausted or the limit stopped it;
use capture hash + flow ID for later lookup. Offset/index is local iteration
state, not an upstream pagination API. Native captures stream; in 12.2.3
FlowReader's HAR branch parses the whole JSON into memory. Bound HAR input size
before opening, use an approved reviewed JSON reader if necessary, and retain
native captures because HAR conversion is lossy for non-HTTP events and identity.
Corrupt/empty files, absent responses and streamed/missing `raw_content` are
explicit cases. `None` body differs from `b""`; decoding/compression can fail.
Selected body lookup is a separate private extraction, with byte/encoding limits
and reviewed release. Do not automatically print headers/URLs/body in this loop.

## Offline frontend versus capture/replay

For an approved small native input, direct v12.2.3 offline HAR conversion:

```bash
mitmdump -n -q --set confdir="$MITM_STATE" --set keepserving=false \
  -r "$CAPTURE" --set hardump="$PRIVATE_HAR"
```

`-n` disables proxy listeners; `-r` reads, `-w` saves native flows, `-s` runs addon
code, `--set` supplies options. Reading dispatches lifecycle hooks and addons can
execute code/send traffic; `-n` is not a sandbox or network enforcement boundary.
Use only reviewed addons/config and dedicated owned confdir. HAR output stays
private, skips non-HTTP events and is not redacted by format conversion.

Live capture requires explicit listener/mode/endpoint, dedicated CA/confdir,
owned process/readiness, recorded capture mode and finite duration/storage budget.
Filters select output, not outbound authorization. TLS verification stays enabled.
Client replay sends traffic; server replay needs scoped unmatched-request behavior
tests before use. Read installed options and tested fixtures instead of
inventing replay flags. Replay/modification is distinct from offline reading.

## Variants

- mitmdump: headless CLI/Python addons. mitmproxy TUI/mitmweb: human companions,
  not automated interfaces; web admin exposure needs separate review.
- Forward: client proxy/trust settings. Reverse: explicit controlled upstream,
  with host/target rewriting differences. Upstream: another proxy and credentials.
- WireGuard/local capture: platform/privilege/routing-dependent optional modes,
  need bounded compatibility experiments and authorization, not an automatic
  substitute when forward capture fails.
- User/system/debug CAs and pinning determine Android trust; proxy visibility
  is not universal TLS interception. HTTP/2, WebSocket, TCP, UDP and streaming
  have distinct event/body contracts; HTTP summaries cannot prove their absence.
- Addons receive request/response/error/protocol events; hooks may occur before
  body completion. Mutating a flow changes the experiment. Keep originals and
  baseline, record hook version and every side effect. End only owned capture,
  then finalize artifacts, restore approved routing/trust and report residual state.
