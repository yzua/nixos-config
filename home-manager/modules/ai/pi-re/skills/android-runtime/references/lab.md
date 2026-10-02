# Coordinated rooted lab and traffic

Apply the [open-box contract](../../../contract.md#open-box-autonomy) to the
requested app/lab before boot/root, Frida, capture and **guest system CA** setup.
Recorded owned-fixture and fresh-agent coverage is in the
[README](../../../README.md#verification-and-readiness); arbitrary apps, unknown
samples and broader packs remain outside that evidence.

## Lifecycle

```bash
pi-re lab status --json
pi-re lab start --visible --json
# Optional exact-host narrow mode instead (after stopping an active lab):
# pi-re lab start --allow-host api.example.test --allow-host login.example.test --json
pi-re lab stop --json
```

`start` boots/reuses only the setup-selected owned non-Play API35 emulator,
verifies serial-specific `adb root` and UID0, starts a dedicated mitmdump12.2.3
listener on loopback at the setup-configured port, installs its **public** CA in
the guest, assigns the emulator's `10.0.2.2:<port>` proxy and starts matched Frida.
Default all-hostname forward capture and optional exact-host narrowing follow
the [contract](../../../contract.md#open-box-autonomy). `--allow-host` entries are
exact DNS hostnames, not URLs or wildcard patterns. Different active capture
mode/list/configuration is refused: stop the owned lab before changing it.
`--visible` requests an emulator window; without it launch is headless. Setup
selects SwANGLE software rendering with hardware video decoding disabled. The
selected GPU must appear in matching installed help; no silent renderer fallback.

`status` is metadata/process-only; it does not root/contact Android, inspect flows
or prove current trust/proxy readiness. Start revalidates readiness. Serialize
lab/device mutations; do not mix low-level Android lifecycle commands with an
active coordinated operation. UI observation can use `pi-re device` afterward.

API35 uses Conscrypt's APEX certificate store and zygote mount namespaces. The
installer copies stock public roots plus the dedicated CA into an owned per-boot
certificate directory and bind-mounts it in the lab and current zygote views.
It does **not** disable SELinux, remount the system writable, change the host or
browser trust stores, or send the MITM signing key to Android. Reuse verifies the
certificate in current zygote namespaces. Restart already-running target apps;
their earlier mount namespaces are not rewritten. Boot-scoped overlays disappear
when the VM stops and are reapplied by the next coordinated start. The host CA
is persistent and private so capture restarts do not continually change trust.

`stop` restores only the proxy value it assigned, preserves an external proxy
change, independently stops owned Frida/guest/capture resources and reports cleanup
failures. It first closes the owned UI session and stops only the private device
daemon, then syncs guest filesystems before VM shutdown. Cold starts clear that
private daemon state to avoid cross-boot helper caches. The Nix package patches
upstream's absent `/bin/ps` to pinned procps, preserving recorded-start stop guards.
It holds the lifecycle lock through daemon and capture shutdown. Abrupt host/process
death can retain recorded resources; inspect metadata and use `lab stop` for
recovery, never a global kill or `adb kill-server`. Direct `android stop` is not
a replacement for coordinated cleanup.

## Reproducible owned-fixture check

```bash
pi-re lab check --json
```

This is an explicit provisioning/qualification action with a separate **600-second**
aggregate budget. It only replaces an installed `org.pi.re.fixture` APK after its
signer matches this profile's saved owned APK. It builds the reviewed counter/HTTPS
fixture with pinned local SDK/JDK and short-lived temporary signing material;
no SDK/npm/pip download occurs. The check uses an explicit fixture-only exact-host
configuration, temporarily mapped to a loopback HTTPS origin with a temporary
certificate. It accepts a validated existing all-host or fixture-only capture,
then temporarily replaces that with the isolated fixture test. Other active
exact-host lists or mismatched tool/configuration state are refused.

The check requires all of these, not merely a listening process:

- Selected UID0 and SELinux still Enforcing.
- Actual fresh-reference UI click, Java `increment()` hook event and Counter0→1.
- App `HttpsURLConnection` **default system trust**, without a custom trust manager.
- Verified upstream TLS, matching nonce in UI and exactly one decrypted200 flow.
- Denied unapproved CONNECT host and restoration of the previous owned proxy value.

Reports, Java events and original binary flows remain private under the caller's
RE state. The check leaves default all-host forward capture running on success,
without the
expired loopback-origin mapping. Failure attempts independent whole-lab cleanup;
inspect any recovery warnings. A Frida graceful-stop timeout can be reported even
when subsequent verified VM shutdown removes that guest process; do not confuse
that warning with a still-running server or silently discard it. Raw flows are not automatically sanitized release
artifacts. This check measures the owned tool path; fresh-agent trial coverage
is reported separately in the README, not inferred from this check.

## Java bridge outside the native probe

Use the installed pinned CLI or Python with its local bundled Java bridge for
scoped hooks; read [Frida bridge details](frida.md#version-and-bridge-authority).
After owned root/server/package readiness, task JavaScript can use:

```bash
frida -D "$LAB_SERIAL" -N "$APPROVED_PACKAGE" -l "$REVIEWED_HOOK_JS" -q -t 15 --exit-on-error
```

Use an outer finite deadline too. Wait for an explicit hook-ready message before
the correlated action, record the subsequent event and changed UI, then detach.
The attach-only `pi-re frida run --script` native probe still does **not** implicitly
supply Java or retain a long observation window; do not use it to claim a later
UI event. `lab check` explicitly loads the pinned bundled bridge through Python.
System CA trust does not bypass certificate pinning, root detection or hardware-
backed Play Integrity. Those require separately authorized analysis and cannot be
promised to work on this emulator.
