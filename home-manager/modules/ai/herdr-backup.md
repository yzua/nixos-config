# Herdr layout recovery backups

`herdr-backup.nix` provides an independent Home Manager activation backup and a
five-minute user timer. It never restores a layout, restarts a server, or stops
panes. Copies preserve layout and agent references, not running processes.

## Storage and compatibility

Inputs are the configured Herdr `session.json` and named sessions under
`sessions/*/session.json`. Private recovery data lives under
`${XDG_STATE_HOME:-$HOME/.local/state}/herdr-layout-backups/`:

- `default/` and `named-<session>/` have separate histories.
- `latest.json` is the last observed valid layout.
- Up to **96 changed snapshots** and **8 daily copies** are retained per session.
- Directories are caller-owned and mode **0700**; recovery files are **0600**.

The helper accepts nonempty current **v3** layouts, checks required structure,
recognized metadata types, valid UTF-8 strings and BSP pane references against
[Herdr v0.9.3's snapshot schema](https://github.com/herdrdev/herdr/blob/v0.9.3/src/persist/snapshot.rs),
and preserves original JSON bytes. Legacy v0–v2, future versions, empty layouts,
and corrupt input are skipped rather than replacing the last valid recovery.
Unknown additive fields remain compatible when their JSON is valid.

Reads use non-following, nonblocking descriptors, a 16 MiB limit, and stable inode
metadata. Existing recovery folders are audited even after live-layout loss or
named-session deletion. Unsafe hardlinked/permissive recovery files are replaced
atomically while preserving their historical contents; symlink/nonregular history
fails closed. These checks cannot undo data already disclosed through an external
alias and do not contain malicious processes running as the same user.

## Failure and recovery

Activation warns and continues on backup/readiness errors. The timer reports
filesystem/lock failures and has a one-minute deadline. Concurrent backup runs
fail promptly instead of waiting indefinitely. A stale selected/default Herdr
server produces a warning only; installing a new binary does not replace a
running compatible old server.

Recovery is manual: save work, stop only the affected server from outside Herdr,
preserve its current layout, review one private backup, copy it into that
session's `session.json`, and restart. Server stops end pane processes. Agent
restoration requires valid native references and compatible integrations.
Unsampled changes and power loss before a save remain limitations.

## Verification

`python3 -B tests/herdr-backup.py` exercises private synthetic state: valid and
malformed schema, rotation, unsafe aliases/locks, source races, recovery-only
histories, readiness warnings and unchanged live-input bytes/metadata. It does
not reboot the host, restore real layouts, or stop a live server.
