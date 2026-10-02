# Reviewed Chrome DevTools CLI interface

## Source and version

Reviewed executable baseline: `chrome-devtools-mcp` **1.10.1** exposing
`chrome-devtools`. Primary matching release
[CLI](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/chrome-devtools-mcp-v1.10.1/docs/cli.md),
[configuration](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/chrome-devtools-mcp-v1.10.1/docs/configuration.md),
[tools](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/chrome-devtools-mcp-v1.10.1/docs/tool-reference.md),
[README/privacy](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/chrome-devtools-mcp-v1.10.1/README.md).
Derivative skill baseline commit:
`ae0aaef884c41445d83f86f099ef211f4584b791`.
Confirm detected executable/browser/runtime versions and installed command help.
A skill commit is not compatibility certification for the executable.

## Dedicated lifecycle gate

CLI calls can implicitly start/reuse a background daemon/browser. Before the
first call require a compatible **dedicated RE daemon endpoint and browser profile**
with ownership/identity evidence. Do not attach to personal/default coding browser
state, use ambient auto-connect, or infer isolation from an isolated tab context.
If the actual CLI cannot prove distinct daemon routing/state, report blocked;
no guessed daemon-socket flag or `pi-re browser` launcher is supplied here.

During approved managed setup, read `chrome-devtools start --help` for supported
forwarded options. `start` can restart a daemon and `stop` affects its instance;
both require verified dedicated ownership, not per-query routine use. Normal
commands reuse that verified instance; close only pages/contexts this run created.
Do not use a global stop/start/uninstall recipe on an uncertain instance.

The CLI defaults to unrestricted filesystem access even though the server's
roots defaults differ. 1.10.1 supports `--workspace` for reviewed file roots;
`--allow-unrestricted-paths` compatibility spelling cannot be combined with it.
Use installed start help to verify supported options; path restrictions are not
process isolation or evidence sanitization. Target browser/node child processes
can still see host/profile data under host mode.

Provisioning policy should disable usage statistics, CrUX URL submission and
update checks: matching source documents `--no-usage-statistics`,
`--no-performance-crux`, `CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS` and
`CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS`. Confirm CLI forwarding/help and actual
managed configuration before using the capability. Source maps, browser network
background work and downloads also require exposure review. No installation or
telemetry repair is performed by this guide.

## Minimal selected-page queries

On an existing verified dedicated instance, all content already approved:

```bash
chrome-devtools new_page "$MOCK_URL" --output-format=json
# PAGE_ID is the returned owned page ID; never substitute another page.
chrome-devtools take_snapshot "$PAGE_ID" --output-format=json
chrome-devtools list_network_requests "$PAGE_ID" \
  --pageSize 25 --pageIdx 0 --output-format=json
chrome-devtools get_network_request "$PAGE_ID" --reqid "$REQUEST_ID" \
  --responseFilePath "$PRIVATE_BODY" --output-format=json
chrome-devtools close_page "$PAGE_ID"
```

Expected: owned page identity, snapshot UIDs, bounded network summary page and
selected request/body reference, then checked page closure. Pagination does not
bound each line/body; save output privately under an external 30-second query
and byte/storage limit, release only approved selected fields. Request detail
can itself expose secrets even when body is written to a private path.
`--output-format=json` returns raw tool JSON, not a guaranteed sanitized schema.

Use installed per-command `--help` before parameters vary. Page-scoped tools
use explicit page IDs; `evaluate_script` uses `--pageId`. Select one request ID
from the bounded list rather than the ambient selected request. Network request
IDs and snapshot UIDs are scoped state; preserve page/run/time identity.

## Branches and limits

- Inspect → act → verify: snapshot UIDs for click/fill; refresh after navigation/
  DOM change. Use only current owned-page UIDs, never another task's selection.
- Navigation/input/submission can send traffic. Live origins/accounts/redirects,
  uploads/downloads and arbitrary JS evaluation are distinct authorized actions.
  Do not put passwords/tokens into model-visible fill arguments/history.
- Browser page/profile/context separates state, not OS processes/network scope.
  Allow/block URL pattern support depends on browser version (allowed patterns
  require Chrome 149+ in reviewed source); it is not a host sandbox guarantee.
- CLI JSON versus readable text: either is valid evidence after release; JSON
  does not sanitize UI strings, console/network diagnostics or binary artifacts.
- Experimental CLI excludes some MCP commands; extensions/PWA/vision/WebMCP/
  memory/trace families need actual availability, compatibility and bounded
  coverage tests under the shared policy. MCP integration remains disabled.
  Do not assume installed skill recipes describe an enabled CLI command.
- Chrome/Chrome for Testing are upstream supported; arbitrary Chromium forks
  are not certified. Playwright fixtures are a separate binding/browser family,
  not attachment to this arbitrary daemon. Load web-protocol for scripted tests.
- A missing request/body, dropped log, failed navigation or partial snapshot
  is not proof of absence. Preserve errors/timeout, and recheck owned state before
  retrying non-idempotent actions. Close owned pages and report remaining state.
