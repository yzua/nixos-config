# NixOS + Home Manager

Workstation configuration with standalone Home Manager. NixOS manages the
system; Home Manager manages user apps and preferences.

## Usage

Run commands from the repo root. Use `nix develop` if the tools are missing.
On a configured machine, ordinary commands detect the system output by hostname
and the Home Manager output by `username@hostname`:

```sh
just preview
just switch
just home-preview
just home-switch
```

Explicit selectors override detection for cross-host builds. If several outputs
exist and no local name matches, the scripts refuse to guess:

```sh
nix eval --json --no-write-lock-file .#nixosConfigurations --apply builtins.attrNames
nix eval --json --no-write-lock-file .#homeConfigurations --apply builtins.attrNames
export NIXOS_CONFIG='<selected-system-output>'
export HOME_CONFIG='<selected-home-output>'
```

Selectors choose a configuration, not a remote activation target. Home Manager
preview, status, and switch require the selected username and home directory to
match the caller. Both current Home outputs share that owner, so selecting the
other host's Home output can apply its preferences **locally**. For a build-only
check of another owner's Home output, bypass the local-state workflow:

```sh
nix build --no-link --no-write-lock-file \
  ".#homeConfigurations.\"${HOME_CONFIG}\".activationPackage"
```

The desktop and MacBook share tools, account preferences, and dependency pins.
The laptop keeps its generated storage/Broadcom configuration and installed state
version, adds Intel graphics, Retina scaling, touchpad and power management, and
retains GNOME as a fallback to Niri. Its Home Manager profile includes the
on-demand Android/RE lab and large multilingual voice model, but omits gaming,
OpenDesign, and unrelated desktop AI applications. Mullvad, NetBird, and Tailscale
have separate device enrollment. The normal desktop apps and VPN UIs start with
Niri; the emulator remains on-demand. See [MacBook hardware and readiness notes](hosts/macbook/README.md)
for camera/video support, resource limits, VPN prerequisites, and remaining checks.
Output names derive from `setup` and `laptopSetup` in `flake.nix`; list them with
the commands above rather than assuming account or host names. Laptop remote
administration uses key-only OpenSSH; authorized keys remain user-owned in
`~/.ssh/authorized_keys`.

Plaintext credentials and private decryption keys stay outside Git and the Nix
store; SOPS-encrypted secret files may be committed. Transfer only selected
mutable auth/config files over verified SSH with private file permissions;
Git signing keys, GitHub CLI authentication, and API logins are separate.
Copying GitHub CLI's configuration alone does not migrate a keyring-backed token.
OpenCode 2 also stores credentials separately from provider configuration; use
its `auth export` / `auth import` commands through a private pipe, never a log
or repository file. Successful credential import does not prove a provider's
model catalog or inference works.

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

The desktop's [headset playback tuning](docs/audio.md) starts EasyEffects at login
with a reversible EQ preset; microphone processing is unchanged.
[Peripheral controls](docs/peripherals.md) cover mouse settings, scoped RGB tools,
automatic white-light restoration, and cooler telemetry without fan/pump-speed changes.
[Steam and custom Proton runners](docs/steam.md) covers per-game GE-Proton and
Proton-CachyOS selection and the existing GameMode/MangoHud launch options.
[Enter The Wired](docs/enter-the-wired.md) covers the pinned ACCELA/SLSsteam
packages, writable settings, Steam compatibility checks, and removal.
[TV game streaming](docs/game-streaming.md) covers Moonlight, DualSense input, and
the reversible 16:9 Steam Big Picture entry.
[Room Cam](docs/room-camera.md) provides on-demand full-resolution viewing,
local person alerts, and a hand-landmark/gesture data playground, without
recording or remote access.

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
With multiple outputs, local hostname/user matches are automatic; use
`NIXOS_CONFIG` or `HOME_CONFIG` to deliberately select another output.

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
With the laptop outputs selected, `python3 -B tests/laptop-profile.py` evaluates
its hardware, lab/voice, VPN, power, and key-only SSH invariants without building
or activating.
Run `just test` for the explicit offline regression suites, including generation
workflows, voice actions, Pi extensions/subagents, and the RE profile/lab mocks.
These tests use isolated fixtures without activation or paid model calls.
The default `nix develop` shell alone does not supply all test prerequisites.
Generated-config tests require managed Niri and tmux; local-source skill tests
require the managed skills CLI. Pi suites also require Node.js, Herdr, Bun,
managed Pi, and installed web-fetch dependencies;
`PI_BIN` and `PI_WEB_FETCH_DIR` can select alternate installations. Ordinary Pi
suites share lazy resource checks and inherited-session isolation in
`tests/pi_test_support.py`; direct runs use the same checks as the aggregate
preflight. Live desktop focus, browser, and Android lab checks remain separate
opt-in commands.
`just test-preview-roots-gc` separately verifies preview retention by running GC
only in a disposable local Nix store, never on the workstation store.

[Agent Reach](docs/agent-reach.md) adds a pinned CLI for public and browser-backed
platform searches, with explicit login handling for X and Reddit.

## Pi profiles

`pi` remains an alias for `pi-coding` (and `p` still adds project approval).
[Pi base](home-manager/modules/ai/pi-base/README.md) owns common extensions and the
one live login/model/global settings configuration at the existing `~/.pi/agent`.
Web search, web/PDF fetching, interactive subagents and the Chrome DevTools CLI/skill
are shared by all root profiles;
RE additionally retains its specialized restricted workers.
Coding retains native discovery/history; `pi-re` and `pi-home` use separate histories
and explicit domain loadouts. Herdr's `pi --session` restore routes each root back
to its owning profile and rejects headless worker artifacts.

Close legacy RE sessions before the first Home Manager activation. Migration privately
archives their original auth/models/settings and merges compatible RE-only
providers, models and logins into the shared configuration. Current Pi defaults
and conflicting values stay unchanged. No activation is needed just to evaluate or preview. [Pi Home](home-manager/modules/ai/pi-home/README.md)
adds personal assistance and on-demand Samsung TV controls; it starts no TV connection
or background service. Device actions require an explicit request.

## Layout

- `docs/`: local operating guides and historical research. Research is not a
  current package or readiness inventory; most notes are intentionally Git-ignored.
- `flake.nix` and `flake.lock`: outputs and pinned dependencies.
- `hosts/`: hardware and host settings. `modules/nixos/` holds reusable system
  settings, grouped into `desktop/` infrastructure and `networking/` VPN/Tor
  services, with explicit imports in each host.
- `packages/`: custom package definitions and their sources, shared by flake
  outputs and profiles.
- `home-manager/`: user apps and preferences. Under `modules/`, `desktop/`
  groups GNOME, Niri, and Noctalia settings; `desktop-apps/` owns applications;
  `terminal/` groups CLI tools, terminal/shell settings, tmux, and Git.
  The desktop entry point is `home-manager/home.nix`; the laptop has its own
  import list in `home-manager/laptop.nix`.
  [Shared skills ownership](home-manager/modules/ai/skills.md) explains pinned
  preparation, mutable installed copies, and installation limitations.
- `justfile`: command menu and checks; `scripts/generation.sh`: build/review policy,
  status, and guarded switches; `scripts/saved-preview-build.sh`: saved-preview
  lifecycle and freshness.

## License

Licensed under the [WTFPL, version 2](LICENSE).
