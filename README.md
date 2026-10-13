# NixOS + Home Manager

Workstation configuration with standalone Home Manager. NixOS manages the
system; Home Manager manages user apps and preferences.

## Usage

Run commands from the repo root. Use `nix develop` if the tools are missing.

```sh
just check          # validate the configuration
just status         # show active, previewed, and desired generations
```

These commands do not build or activate anything. Stage new `.nix` files
before checking, because Git flakes ignore untracked files.

For user apps and settings:

```sh
just home-preview   # build and review changes
just home-switch    # apply the reviewed build, without sudo
```

For system settings:

```sh
just preview        # build and review changes
just switch         # apply the reviewed build
```

Review each preview before switching. Switches require a current saved preview
and check the system hostname or Home Manager user and home directory.
When moving apps from NixOS to Home Manager, apply Home Manager first.
Successful previews retain their builds with per-output GC roots under the caller's
XDG state directory. Failed builds or reviews leave the previous saved preview intact.
With multiple outputs, select one using `NIXOS_CONFIG` or `HOME_CONFIG`.

Development tools come from the pinned Nixpkgs input; no npm or pip install is
needed. In `nix develop`, run `just fmt` to format files, `just fmt-check` for a
read-only formatting check, and `just lint` for static analysis. Biome handles
the locally owned TypeScript sources; Ruff handles Python formatting, import
ordering, and common mistakes. Package lockfiles stay outside the formatter.
Biome keeps its recommended rules with a few style and extension-interop
exceptions; missing callback returns and unused code still get checked.
ShellCheck checks Bash; shfmt formats it. Rust-based rumdl checks and formats
Markdown, including links and structures that affect rendering, without
requiring line wrapping or headings in prompt fragments. For quick focused
checks, use `just lint-ts`, `just lint-python`, `just lint-shell`, or
`just lint-markdown`.
Run `just test` for the explicit offline regression suites, including generation
workflows, voice actions, Pi extensions/subagents, and the RE profile/lab mocks.
These tests use isolated fixtures without activation or paid model calls.
Generated-config tests require managed Niri and tmux; local-source skill tests
require the managed skills CLI. The loader tests require managed Pi, Bun, and
installed web-fetch dependencies;
`PI_BIN` and `PI_WEB_FETCH_DIR` can select alternate installations. Ordinary Pi
suites share lazy resource checks and inherited-session isolation in
`tests/pi_test_support.py`; direct runs use the same checks as the aggregate
preflight. Live desktop focus, browser, and Android lab checks remain separate
opt-in commands.
`just test-preview-roots-gc` separately verifies preview retention by running GC
only in a disposable local Nix store, never on the workstation store.

## OpenDesign

OpenDesign is installed by Home Manager as a local browser workspace, built
from the pinned upstream `open-design-v0.24.1` release. Linux has no official
prebuilt desktop release yet; this package builds the daemon and static web UI,
not the Electron shell. The release's embedded API version still reports `0.23.1`.

After reviewing `just home-preview` and applying `just home-switch`, launch
**OpenDesign** from the application menu or run:

```sh
open-design                 # start the workspace and open your browser
open-design --no-open       # start without opening a browser
open-design --help          # upstream CLI commands (called od in its help)
```

Open <http://127.0.0.1:7456> while the command is running. The menu launcher
keeps a terminal open; press **Ctrl+C** to stop. Nothing starts at login.
The command deliberately does not replace the system's `od` utility.

The launcher defaults `OD_DATA_DIR` to the caller's XDG data directory under
`open-design`, and binds to localhost. Projects, settings, and credentials
remain writable and outside the Nix store; Home Manager does not manage them.
For upstream data ownership rules, see the pinned release's
[daemon data directory contract](https://github.com/nexu-io/open-design/blob/89e64d813bb1c7a11519b3f668f011f7017637d7/AGENTS.md#daemon-data-directory-contract).
Installed agent CLIs remain discoverable through the caller's PATH. Choose
**Local AI** during onboarding and authenticate the agent normally; no API keys
are added to this configuration. HyperFrames uses the configured Nix-managed
Chrome instead of downloading a browser. The DeepSeek Harness connection
component is bundled, but the official `dsh` CLI is not installed by this module. OpenDesign's bundled skills stay inside the app rather than
replacing the shared skills managed by this repository.

The source and npm dependencies are hash-pinned. Packaging uses maintained
pnpm with a compatibility adjustment that preserves the upstream lockfile,
rather than enabling Nixpkgs's insecure pnpm 10. A targeted build is available
with `nix build .#open-design`; frontend/native-addon changes require a local
build. To smoke-test a built package with temporary data and a mock agent:

```sh
python3 tests/open-design.py "$(nix build .#open-design --no-link --print-out-paths)/bin/open-design"
```

A temporary native-addon build workaround restores the pre-24.19 `ObjectWrap`
cleanup behavior in copied headers, without downgrading the Node runtime.
This avoids the [Node 24 cleanup-hook regression](https://github.com/nodejs/node/issues/65446)
that aborts OpenDesign during SQLite statement collection. The package build
runs `tests/open-design-native.cjs` through stdin to catch this exact failure;
remove the workaround once a verified Node runtime fix is available.

Browser automation and media/export workflows may require additional
upstream tool setup and are not covered by the basic workspace smoke checks.
Local-first does not mean offline: model/cloud requests and upstream telemetry
can contact external services; review the app's privacy settings before use.

## Gaming

Niri opens Steam game windows fullscreen automatically. Fullscreen alone does
not guarantee mouse confinement: for Proton games on multiple monitors, close
all Proton/Wine games and run `steam-mouse-grab` to enable Wine's
`GrabFullscreen` setting in existing game prefixes across your Steam libraries.
The command preserves other registry settings and saves a
`user.reg.before-mouse-grab` backup beside each changed registry. It refuses to
edit while a Wine server is running.

New games create their own prefixes on first launch; close them and rerun the
command afterward. Nothing is applied continuously or to native Linux games.
Use **Super + Shift + F** to toggle Niri fullscreen and **Alt + Tab** to switch
away. To undo confinement, close the game and remove `"GrabFullscreen"="Y"`
from its `pfx/user.reg` section `[Software\\Wine\\X11 Driver]`; avoid restoring
an old whole-registry backup after the game has made other settings changes.

## Layout

- `flake.nix` and `flake.lock`: outputs and pinned dependencies.
- `hosts/`: hardware and host settings. `modules/nixos/` holds reusable system
  settings, grouped into `desktop/` infrastructure and `networking/` VPN/Tor
  services, with explicit imports in each host.
- `packages/`: custom package definitions and their sources, shared by flake
  outputs and profiles.
- `home-manager/`: user apps and preferences. Under `modules/`, `desktop/`
  groups GNOME, Niri, and Noctalia settings; `desktop-apps/` owns applications;
  `terminal/` groups CLI tools, terminal/shell settings, tmux, and Git.
  [Shared skills ownership](home-manager/modules/ai/skills.md) explains pinned
  preparation, mutable installed copies, and installation limitations.
- `justfile`: command menu and checks; `scripts/generation.sh`: build/review policy,
  status, and guarded switches; `scripts/saved-preview-build.sh`: saved-preview
  lifecycle and freshness.

## License

Licensed under the [WTFPL, version 2](LICENSE).
