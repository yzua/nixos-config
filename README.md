# NixOS configuration

The `PC` NixOS flake output uses `hosts/PC/default.nix`. This host entrypoint
imports its generated `hardware-configuration.nix`, plus shared
`modules/nixos/base.nix` (locale and system tools),
`modules/nixos/development.nix` (system-wide Node.js and pnpm),
`modules/nixos/gnome.nix` (GNOME, IBus, audio, printing),
`modules/nixos/mullvad-vpn.nix` (Mullvad VPN daemon and GUI), and
`modules/nixos/numtide-cache.nix` (Numtide binary cache). A future
host can import whichever shared modules it needs while keeping its own
hardware, boot settings, hostname, and `system.stateVersion`.

The standalone Home Manager output `yz@PC` uses `home-manager/home.nix`, which
imports modules for GNOME's English/Arabic input sources, Firefox, MIME
defaults, KeePassXC, desktop apps (including Vesktop through Nixcord), everyday
CLI tools, AI tools, and user-level SOPS secrets.
`home-manager/modules/ai.nix` lists AI tools supplied by the pinned
`llm-agents.nix` input (which keeps its own Nixpkgs pin).
As features grow, add files under `home-manager/modules/` and list them in
`home-manager/home.nix`'s `imports`; the standalone flake output stays the same.
The lock file pins Nixpkgs and Home Manager to matching 26.05 release branches;
nothing from the old configuration is imported.

Git flakes use tracked files as their source. Stage each new `.nix` file with
`git add` before checking or previewing; otherwise Nix will not see it.
The repo's `.gitignore` filters local build links and common plaintext
credential copies. The Home Manager Git module supplies a separate, narrow
global ignore for editor and OS leftovers; it does not hide `.env` files or
build output in unrelated repos. Neither layer hides Nix modules, `flake.lock`,
`.sops.yaml`, encrypted `secrets/*.yaml`, agent instructions, or documentation.
Ignore rules are not a secret scanner and do not hide files already tracked;
review `git diff --cached` before committing.

From the repository root, run `just check` to check Nix file headers, evaluate
both configurations, check repo-declared package lists for duplicates, and warn
about untracked Nix files. `just headers` quickly checks tracked and untracked
Nix files for a first-line purpose comment; `just verify` runs only the no-build
flake check; `just pkgs` runs only the package check. `just status` compares
active, saved preview, and desired system/home generations without building or
switching.

The `justfile` is the entry point for the helpers under `scripts/`:
`config.sh` selects and validates flake outputs for recipes and checkers;
`saved-preview-build.sh` shares the saved-path guard and Home profile location;
`home-switch.sh` activates the validated Home generation without rebuilding;
`home-preview.sh` reviews the closure, managed files, and declared GNOME input
sources alongside their current dconf value;
`check-nix-headers.sh` backs `just headers`; `check-packages.sh` backs
`just pkgs` and checks only this repo's explicit package declarations (not
packages added implicitly by NixOS or Home Manager); `status.sh` backs
`just status` and compares active, saved, and desired generations without
building.
`bash tests/workflow.sh` exercises selection, stale-build guards, and read-only
input-source preview with temporary generations; it never activates a real one.

Development tools live only in the flake's dev shell, not in the installed
NixOS or Home Manager profiles. It uses the pinned Nixpkgs packages: the
[official nixfmt](https://github.com/NixOS/nixfmt) through `nixfmt-tree` for
Nix files, `shfmt` for shell scripts (2-space indentation), `statix` and
`deadnix` for Nix linting, and ShellCheck for shell linting. `just` formats its
own justfile. The shell also includes `sops` and `age` for encrypted secrets.
No Git hook or background formatter is needed.
The generated `hardware-configuration.nix` is exempt from formatting and
dead-code checks; `statix.toml` permits idiomatic repeated dotted option paths.

```sh
nix develop --no-write-lock-file . -c just fmt-check  # read-only format check
nix develop --no-write-lock-file . -c just lint       # static analysis
nix develop --no-write-lock-file . -c just fmt        # rewrite Nix, shell, justfile
```

Once inside `nix develop`, run the same `just` recipes directly. `nix fmt`
uses the same Nix/shell formatter; `just check` stays a header, evaluation,
and package-list check rather than building lint tooling or rewriting files.

The recipes select the output matching the running hostname and login when
possible, or a sole output. If selection is ambiguous, set `NIXOS_CONFIG`
and/or `HOME_CONFIG` to the intended flake output names. Activation still
checks that the selected NixOS hostname matches the running host and that the
Home Manager username and home directory match the caller.
Home-only recipes can select an explicit `HOME_CONFIG` without resolving any
NixOS output. When a caller needs both outputs, it selects the NixOS output
first and uses that host as context for Home selection.

`just build` builds the NixOS closure without activating it; `just preview`
builds it and diffs it against `/run/current-system`. Review that preview
before `just switch`, which activates the saved build only if it still matches
the flake. This host's rename from `nixos` to `PC` is migration history:
`ALLOW_HOST_RENAME=1` is only for a deliberately approved hostname change,
not a normal switch or a way to bypass a wrong output selection.

Home Manager is standalone and separate from the NixOS switch. Telegram,
Firefox, KeePassXC, GitHub CLI (`gh`), Wayland clipboard tools
(`wl-clipboard`), and the CLI tools in `home-manager/modules/cli.nix` are user
packages; NixOS provides Node.js/npm and pnpm for all users, including root.
Chrome, VS Code, and OBS Studio are also Home Manager packages; OBS has no
extra plugins. Nixcord manages Vesktop without installing Discord separately
or rebuilding the cached stock Vesktop package. Mullvad VPN is instead a
NixOS service with the GUI package; it does not declare auto-connect or extra
early-boot traffic blocking. Firefox remains the default browser for links.
Firefox declares Personal and Work with stable profile paths. Removing the old
Personal path override leaves that older profile on disk but selects a new
`personal` profile on the next Home Manager switch.
Both profiles use DuckDuckGo for normal and private search and have a few
non-breaking privacy/comfort preferences. Password
databases, logins, and Firefox Sync remain unmanaged; Home Manager does not
manage your shell.
Run `just home-preview` to build and compare it with an existing Home Manager
profile, review managed home files, and see active and desired GNOME input
sources. Those sources are dconf settings, not managed files; GVariant type
annotations may make the two displayed values look different even when their
content agrees. No other dconf values or decrypted secrets are printed.
`just home-switch` runs without sudo. It verifies the selected user, home
directory, and saved build, then installs and activates that **exact** Home
Manager generation without another flake build. Both switch recipes reject
missing or stale saved builds; neither `check` nor `status` activates anything.

After a reviewed `just home-switch`, sign in interactively with `gh auth login`
and check with `gh auth status`. On Wayland, `wl-clipboard` lets `gh` copy the
one-time code; Firefox is the web URL handler in `home-manager/modules/mime.nix`.
To explicitly use Firefox for the login flow, run `GH_BROWSER=firefox gh auth login`
and press Enter at the URL prompt rather than clicking the terminal's hyperlink.
For HTTPS GitHub remotes, run
`gh auth setup-git` after login to use `gh` as Git's credential helper; for
SSH remotes, register an SSH key with GitHub instead. GitHub login data and
the credential-helper settings in `~/.gitconfig` remain outside Home Manager
and the Nix store. A Git commit is local: to publish it, first connect the
checkout to a repository you own if it has no remote
(`git remote add origin <repo-url>`), then push reviewed commits with
`git push -u origin HEAD`.

### Git identity and SSH signing

`home-manager/modules/git.nix` manages `~/.config/git/config` and a global
`commit-msg` hook; NixOS still supplies the Git executable. The dedicated
`home-manager/home.nix` profile sets this account's name and default SimpleLogin
email, and selects its GitHub noreply address for GitHub HTTPS or SSH remotes.
Repository-local Git identity settings still take precedence. The conventional
commit hook accepts subjects such as `feat(cli): add a command`, permits Git's
merge/fixup messages, and runs a repository's own `.git/hooks/commit-msg` if
present. The old config's GPG key, secret scanner, and push gate are **not**
automatically migrated.

Commits and annotated tags use SSH signing through the user's agent and the
public key at `~/.ssh/id_ed25519.pub`. No private key is copied into Git or
the Nix store. Local `git verify-commit HEAD` checks the signature against the
user-owned `${XDG_CONFIG_HOME:-$HOME/.config}/git/allowed_signers` file. On this
machine that file was created from the public key for both configured email
addresses, outside Git and the store (mode `0600`). Provision it with each
author email and its public key on other accounts, and update it when a key or
email changes. Signing requires the matching private key to be loaded in the
SSH agent. GitHub's **Verified** badge additionally requires registering the
public key with GitHub as a *signing* key, separate from local verification;
do not assume authentication-key registration is sufficient. Check the GitHub
account's signing keys before using `gh ssh-key add <public-key-file> --type signing`.

`home-manager/modules/mime.nix` is the single place for application defaults.
It preserves the existing Firefox web and Telegram URL associations. On this
machine, the previous `mimeapps.list`, Firefox `profiles.ini`, and Personal
profile's `search.json.mozlz4` were backed up under
`${XDG_STATE_HOME:-$HOME/.local/state}/nixos/firefox-mime-backup.*` before Home
Manager took ownership. Edit the modules rather than the managed symlinks.
KeePassXC's browser native-messaging host is installed, but its browser
extension and any password database are not configured.

### Encrypted user secrets

The SOPS recipient policy in `.sops.yaml` contains **public keys only**: a
primary editor identity and an offline recovery identity. The private primary
age key belongs outside Git at `${XDG_CONFIG_HOME:-$HOME/.config}/sops/age/keys.txt`
(mode `0600`, with private parent directories). On this machine it was restored
from removable backup, along with the SSH pair at `~/.ssh/id_ed25519` (`0600`)
and `~/.ssh/id_ed25519.pub` (`0644`). The recovery age identity stays on the
backup, not on the working machine. On another machine, install the appropriate
identity securely before trying to decrypt secrets. Do not manage private keys,
SSH identities, or plaintext credentials as Nix files or Home Manager `home.file`.

The standalone Home Manager output imports `sops-nix` and points it to the
user's age key. `secrets/test.yaml` contains only an encrypted, harmless test
value, declared as `sops.secrets.test` in `home-manager/modules/secrets.nix`.
After a reviewed Home Manager switch, the user service decrypts it at runtime;
its path is `config.sops.secrets.test.path`. **No real secrets from the old
configuration have been migrated, and this change does not activate anything.**
Create only the additional secrets an application needs:

```sh
nix develop --no-write-lock-file .
mkdir -p secrets
sops secrets/example.yaml             # edit encrypted YAML, never plaintext in Git
```

For a user-owned secret, declare it in `home-manager/modules/secrets.nix`:

```nix
sops.secrets.example.sopsFile = ../../secrets/example.yaml;
```

Use `config.sops.secrets.example.path` in its consumer. Stage the encrypted `.yaml`
file before evaluating a Git flake. Once a secret is declared, the Home Manager
user service decrypts it into the runtime directory; order dependent user
services after `sops-nix.service`. Check that the file contains SOPS metadata
and encrypted values before committing. Keep credentials out of Nix strings,
command-line arguments, build logs, and the Nix store. Changes to recipients
require `sops updatekeys secrets/example.yaml` for existing encrypted files.

The NixOS system module is intentionally not enabled yet: no system service
consumes a secret. When one does, add `sops-nix.nixosModules.sops` to that
host's `nixosSystem.modules` and provision a **separate, root-owned** decryption
identity outside the store; do not make root's boot-time secret access depend
on a user's home key.
The removable backup uses a filesystem that cannot enforce Unix file modes;
keep it physically secure, ideally use an encrypted backup, and rotate any
identity if it may have been exposed.

The AI module installs Codex CLI, Pi, OpenCode V2 (`opencode2`), Claude Code,
Antigravity CLI (`agy`), ChatGPT (the Linux desktop app also includes Codex),
Claude Desktop, Copilot CLI, T3Code Desktop,
ZCode, `skills`, `ctx`, and `executor` for the Home Manager user. Executor uses
the pinned Numtide binary package; no second input or package entry is needed.
`skills` is the optional installer CLI for unmanaged skills; don't run
`skills update` on the Nix-managed ones. `home-manager/modules/skills.nix`
separately links all `SKILL.md` bundles from a pinned, non-flake
`mattPocockSkills` input into global skill directories. Codex (including its
ChatGPT desktop surface), OpenCode V2, Pi, and Copilot read `~/.agents/skills`;
Claude Code reads `~/.claude/skills`; Antigravity and its CLI use separate
`~/.gemini/` directories. Individual links leave other installed skills and
agent settings alone. Some upstream skills are experimental or agent-specific;
read their instructions before invoking them. Other desktop apps may need
in-app skill installation rather than local files.

Run `just skills-update` to update **only** that skills input to a new upstream
commit, then review the `flake.lock` diff and the changed skill content. Run
`just check` and `just home-preview`, inspect the managed-file/conflict list,
and use `just home-switch` without sudo only after approving the preview.
New upstream `SKILL.md` directories are picked up automatically on update;
there is no network install during activation or background auto-update.
Existing agent settings, login sessions, and credentials remain unmanaged;
adding a CLI must not overwrite them. In particular, `opencode2` does not
replace an existing `opencode` executable. Choose non-secret settings for each
agent before migrating any of its config files into Home Manager; never put
credentials in Nix values or the store.

This host explicitly trusts Numtide's signing key and cache via the NixOS
module. On a host where that change is not yet activated, the Nix daemon
ignores the cache and `just home-preview` could compile substantial Rust/Node
packages locally. Check cache availability before building the AI Home Manager
profile; review `just home-preview` before `just home-switch`. A NixOS preview
also contains any other pending system changes; do not switch it without
reviewing those changes. Updating the `llm-agents.nix` lock pin is a separate
reviewed change, not an automatic update when a CLI starts.

When moving packages or settings from NixOS to Home Manager, activate Home
Manager **before** switching NixOS: `just home-preview`, `just home-switch`,
`just preview`, then `just switch`. This keeps user apps available while
changing system ownership. The `yz@PC` output has the same Home Manager
settings as the former `yz@nixos` output; renaming its key alone needs no
Home Manager activation.

On a fresh installation, if `just` or flakes are not enabled yet, run the
recipes through the flake's development shell from the repository root:

```sh
NIX_CONFIG='experimental-features = nix-command flakes' nix develop . -c just check
NIX_CONFIG='experimental-features = nix-command flakes' nix develop . -c just preview
```

After reviewing the preview, switch **only when you choose to**:

```sh
NIX_CONFIG='experimental-features = nix-command flakes' nix develop . -c just switch
```

Builds save `result-system` or `result-home` links under
`${XDG_STATE_HOME:-$HOME/.local/state}/nixos/`, outside the flake directory.
Unqualified `nixos-rebuild` uses `/etc/nixos`, **not** this flake; use the
`just` recipes from the repository root instead.
