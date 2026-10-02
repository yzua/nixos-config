# Frida wrapper, direct API and version gates

## Implemented owned-lab wrapper

The bundled interface is `pi-re frida setup|status|stop|run`. For `run`, add
`--package <running application package ID>` and optional `--script <JS path>`; those flags
are not setup/status/stop arguments. The wrapper selects the setup-owned emulator,
locks/revalidates its identity and verifies/root-checks it before runtime work.
Rooted lab status precedes the server path. No caller serial/device override.

- `setup`: deploys and starts the matched pinned Android **x86_64** server on the
  selected guest, loopback listener, with owner/boot/version/PID/start metadata;
  rejects foreign listeners/process reuse instead of takeover or downloads.
  Failed ownership publication rolls back through the pidfd helper; if launch
  identity is uncertain, it stops only the verified owned emulator.
- `status`: contacts the selected guest to verify owned server/boot/version.
  It can also invoke owned-lab root verification. This is **not** the no-live-probe
  read-only doctor/Android status interface.
- `stop`: stops only the owned matching server; does not promise to delete all
  guest server/log files, mappings or other persistent state. Record residuals.
- `run`: resolves the application package ID, not its display label, and attaches
  to its **already running process**. It does not spawn or launch an app. Outer run deadline is **30 seconds**; outputs include private
  artifacts, messages and default native RPC probe results. The default probe
  reports PID/arch and up to three module name/size entries, not Java hooks.

Use the [contract](../../../contract.md#interfaces) and shared policy for
capability interpretation. These wrappers' ownership checks remain mandatory;
their native probe is not the limit of in-scope instrumentation.

```bash
# In-scope owned-lab setup and bounded attach:
pi-re frida setup
pi-re frida status
pi-re frida run --package "$RUNNING_PACKAGE"
# Scoped task JS; no default Java bridge or RPC probe is assumed here:
pi-re frida run --package "$RUNNING_PACKAGE" --script "$APPROVED_JS"
pi-re frida stop
```

Expected: owned server state, bounded attach PID/messages/native `rpc` result
(default script only), checked failures/timeout and owned stop. Messages are
limited to 25, individual JSON messages to 2048 characters; binary payloads are
reported by byte count, not retained by the probe. Wrapper output above 16 KiB
returns a partial/truncated artifact reference. These bounds are not redaction;
keep unapproved module names/messages/artifacts private. The default probe uses
native APIs only. User JS can emit secrets or mutate the process; review scope
and evidence release before passing it. A timeout can leave uncertain side effects.

For an action-correlated Java hook, use the direct CLI/Python bridge route below
and the [lab example](lab.md#java-bridge-outside-the-native-probe); wait for hook
readiness before acting. Bare wrapper scripts neither receive Java implicitly
nor retain a later-action observation window.

## Version and bridge authority

Primary references: [Android](https://frida.re/docs/android/),
[Python messages](https://frida.re/docs/messages/),
[JavaScript API](https://frida.re/docs/javascript-api/),
[Frida 17 changes](https://frida.re/news/2025/05/17/frida-17-0-0-released/),
[17.0.0 Python entry points](https://github.com/frida/frida-python/blob/17.0.0/frida/__init__.py),
[17.0.0 session/script/RPC](https://github.com/frida/frida-python/blob/17.0.0/frida/core.py),
[frida-tools](https://github.com/frida/frida-tools).
The direct API shape below is anchored at 17.0.0, not a runtime pin. Record exact
provisioned core/binding/server/tools/bridge versions and selected ABI from approved
metadata/help; use matching installed source for varying methods. Core/server
must match exactly. Tools has a separate version sequence, not numeric equality.
The bundled server branch supports Android x86_64; other ABIs are blocked there.

Frida **17** removes Java/ObjC/Swift bridges from bare GumJS. The pinned official
frida-tools **14.6.1** package supplies a local bundled Java bridge. The supported
CLI loads it lazily; Python-created scripts must load that bundled bridge
explicitly before task JS instead of presuming global `Java`. `lab check` uses
this Python route and correlates a UI click, Java hook and Counter change.
Inspect installed package/source for the bridge API rather than guessing a path;
no npm/pip download or default bare-script Java capability is needed. Native
probes need no Java bridge but still require ABI/address/version checks.

## Direct API for in-scope instrumentation

Write/run scoped JS and Python with installed bindings as ordinary analysis.
Prefer the bundled owner for server/lab lifecycle; direct sessions still need
explicit device/process identity, deadlines and detach cleanup. This task-code
shape demonstrates attach, not a bundled script or Java hook. Bind Frida device
ID to the approved serial and enforce an external process deadline (a message
wait does not bound a stuck attach):

```python
import threading
import frida

seen = threading.Event()
def on_message(message, data):
    # Persist privately under record/byte limits; release approved fields only.
    if message.get("type") in ("send", "error"):
        seen.set()

session = frida.get_device(DEVICE_ID, timeout=5).attach(PID)
script = None
try:
    script = session.create_script('send({kind: "ready"});')
    script.on("message", on_message)
    script.load()
    if not seen.wait(5):
        raise TimeoutError("no script event")
finally:
    try:
        if script is not None:
            script.unload()
    finally:
        session.detach()
```

Expected: one ready/error observation, not target-hook confirmation. Direct spawn
starts a suspended process and requires deliberate attach/load/resume and failure
cleanup within the authorized execution/instrumentation scope; it is
**not supported by wrapper run**. Unknown-sample execution still needs the
contract's whole-process boundary.
Gadget changes app startup/configuration/signing and needs separate approval;
it is not an automatic rootless fallback in this rooted Android environment.

`send(payload, data)` carries messages/binary data; errors include stack fields.
RPC uses JS `rpc.exports` and matching binding `exports_sync`/`exports_async`.
Verify types/error/deadline semantics, and reconcile timed-out mutations. Track
session detach/destroy events and PID/module-relative addresses; unload/detach
owned instrumentation, never kill unrelated attached targets. Empty/error output
is not clean absence. Objection/REPL/MCP are not automatic fallback interfaces.
