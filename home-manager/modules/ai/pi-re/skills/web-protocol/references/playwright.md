# Scripted protocol fixtures with Playwright

Interactive exploration belongs in `re-browser`; this guide is for reproducible
owned tests. Playwright must be available with its matching browser revision and
Node or Python binding; apply the shared policy for untested compatible paths.
Use detected version and version-matched package types/help before writing code. Never run automatic browser installation
or package-manager downloads to make a test pass.

Primary references: [network](https://playwright.dev/docs/network),
[BrowserContext](https://playwright.dev/docs/api/class-browsercontext),
[Page](https://playwright.dev/docs/api/class-page),
[Python](https://playwright.dev/python/docs/network),
[tagged 1.55.0 Node types](https://github.com/microsoft/playwright/blob/v1.55.0/packages/playwright-core/types/types.d.ts).
The 1.55.0 type reference anchors this API shape, not a toolchain pin or tested
combination. Select the installed binding source when versions differ.

## Small owned mock observation

Task code, not a bundled script. Assumes the approved loopback mock returns
non-sensitive fixture content and the installed library/browser are compatible.
Set an external finite test-process deadline in addition to these API timeouts.

```javascript
import { chromium } from 'playwright';

const browser = await chromium.launch();
try {
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    const response = await page.goto(process.env.MOCK_URL, { timeout: 5000 });
    if (!response) throw new Error('no navigation response');
    console.log({ status: response.status() });
  } finally {
    await context.close();
  }
} finally {
  await browser.close();
}
```

Expected: one checked HTTP status from the owned fixture and verified cleanup,
not response bodies/cookies. Launch itself can fail before `browser` exists;
report the error, do not install Chromium. `goto` returning a response does not
make a 4xx/5xx successful application behavior. Context separation is state
separation, not a whole-process sandbox or network scope enforcement.

## Observation versus interception

Use filtered `page.on('request'/'response'/'requestfailed', ...)` and a bounded
selected request to connect action IDs to endpoints/status/time. Limit event
counts and selected bytes before emitting data. Request failure and an HTTP
error response are different events. Bodies, headers, storageState, traces,
HAR and screenshots stay private until approved.

`page.route`/`context.route` modifies traffic; it needs a separate mutation class.
Fixture fulfillment does not prove live server behavior. Service workers, cached
responses, navigation, downloads, redirects and long-lived WebSockets/streams
have separate coverage. Confirm the installed binding's APIs before selecting
stream/frame hooks. Python async/sync API names and lifecycle differ from Node;
use only provisioned bindings and matching docs rather than mixing snippets.

For deterministic tests, name fixture hash, initial cookies/storage state,
operation sequence, assertions, negative/error cases and supported outputs.
Use `waitForResponse` with a precise predicate and finite deadline when needed;
register the wait before the action so a fast response is not missed.
Replay/submit can be non-idempotent; no blind retries. A passing mock test is
contract evidence for those fixtures, not equivalence to an entire private API.

## Other protocols

Use already enabled tools only for an observed need: offline `tshark -r` with a
selected display filter/fields for PCAP; grpcurl for a scoped gRPC call with
schema/reflection assumptions; protobuf decoding for known framing/schema;
OpenSSL for selected TLS/encoding evidence. Read installed help and matching
primary references before commands:
[tshark](https://www.wireshark.org/docs/man-pages/tshark.html),
[grpcurl](https://github.com/fullstorydev/grpcurl),
[protobuf](https://protobuf.dev/), [OpenSSL manuals](https://docs.openssl.org/).
Live capture privilege, reflection requests, TLS connections and streaming have
separate permissions/budgets. Schema-less decoding is inferred structure, not
semantic proof. Unavailable decoders yield blocked, not automatic installation.
