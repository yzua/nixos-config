# Pi Home

`pi-home` inherits the base's pinned Pi, live login/model/global settings and common
extensions and the shared `chrome-devtools-cli` skill/CLI. It adds personal
instructions, an explicit Samsung TV skill and separate
sessions under `${XDG_STATE_HOME:-$HOME/.local/state}/pi-home/sessions`. It suppresses
coding/project resource discovery and disables MCP. Shared interactive subagents
are available, with origin instructions/skills and explicit loadouts preserved on
resume; their histories stay under `pi-home/interactive-subagents/sessions`, separate
from coding history. It does not load specialized RE worker runtimes. These are
loadout boundaries, not a host sandbox.

```sh
pi-home
pi-home --continue
pi-home --resume
pi-home tv --help
```

## On-demand Samsung TV

`setup.pi.home.samsung` in `flake.nix` selects the LAN address and allowed app IDs.
The narrow CLI wraps Nixpkgs `samsungtvws`; it exposes no raw key, root/debug, install,
reset or service interface. The raw upstream CLI is not added to the user's PATH.
No TV request occurs during activation, startup, help or automated tests.

On an explicit request, the following commands contact the configured device:

```sh
pi-home tv info                      # basic identity; no pairing/buttons
pi-home tv volume                    # read numeric volume; no pairing/changes
pi-home tv volume 20 --execute       # one exact set, with numeric read-back
pi-home tv connect                   # authorize, send no buttons, close
pi-home tv key pause --execute       # exactly one allowed button
pi-home tv launch nuvio --execute    # normal launch of the configured app
```

Mutations require both a saved pairing and `--execute`. Exact volume uses Samsung's
LAN UPnP RenderingControl endpoint on port 9197, restricted to GetVolume/SetVolume;
it authenticates the WebSocket first, sets at most once and verifies numeric read-back.
Reads need no pairing. Preserve mute/playback; volume 100 is maximum and requires
explicit confirmation. No hostname discovery, arbitrary SOAP or automatic retry is exposed.
Actions require both a saved pairing and `--execute`. This flag records CLI intent;
it is not an OS permission boundary. The assistant's skill requires a current user
request. Pairing may show an Allow prompt; the user approves it directly. Existing
`${XDG_STATE_HOME:-$HOME/.local/state}/samsung-tv-remote/token` is reused, stays private,
and is never copied into configuration/store/logs. Only one invocation holds the
control lock; a 25-second whole-operation deadline also bounds continuous startup
events and metadata reads. WebSocket/HTTP redirects are refused; every invocation
closes its socket and performs no automatic retry. Device exceptions are sanitized because upstream URLs/events may contain tokens.

Samsung's LAN WebSocket uses its self-signed certificate. The library relaxes
verification only for this configured socket; this does not establish authenticated
TV identity against a hostile LAN. Keep LAN access trusted. No global TLS, VPN or
firewall changes are made. TV off, changed address, denied pairing or blocked LAN
access may cause a bounded failure; setup does not automatically repair networking.

The remote API has no general screenshot/UI tree/focus observation. A successful
send is not proof of the visible UI outcome. The agent works from the user's fresh
screen report; avoid blind navigation sequences. App debugging, data migration and
installation need separate authorization and tooling. No current TV preferences,
app data or Samsung signing certificates are changed by this configuration.

See [base sharing/migration](../pi-base/README.md) for login/default/history semantics.
`python3 -B tests/pi-home-tv.py` uses only fake transports and temporary state.
