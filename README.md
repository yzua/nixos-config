# NixOS + Home Manager

A single-host GNOME configuration built as a Nix flake. NixOS owns the machine;
standalone Home Manager owns user apps and preferences. The current outputs are
`PC` and `yz@PC`. Nixpkgs and Home Manager follow the 26.05 release branches,
and `flake.lock` pins the exact inputs. The old configuration is a reference,
not an import.

**Jump to:** [Quick start](#quick-start) · [Layout](#layout) ·
[Workflow](#workflow) · [Desktop](#desktop-and-user-applications) ·
[Git](#git-and-signing) · [Secrets](#encrypted-user-secrets) ·
[AI tools](#ai-tools-and-caches) · [License](#license)

## Quick start

From the repository root, with Nix flakes and `just` available:

```sh
just check          # evaluate both outputs; do not build or activate
just status         # compare active, saved, and desired generations
just home-preview   # build and review the user generation
just preview        # build and review the NixOS generation
```

Only after reviewing each preview, activate the corresponding saved build:

```sh
just home-switch    # as your normal user, never with sudo
just switch         # NixOS activation; asks for sudo when needed
```

When moving apps or settings from NixOS to Home Manager, **preview and switch
Home Manager before previewing and switching NixOS** so they do not disappear
between activations. Previews can download or build packages; check the
configured binary caches before accepting a large local build. On a fresh
installation without `just` or enabled flakes, run a recipe through the flake's
dev shell, for example:

```sh
NIX_CONFIG='experimental-features = nix-command flakes' nix develop . -c just check
```

## Layout

| Path | Responsibility |
| --- | --- |
| `flake.nix`, `flake.lock` | Pinned inputs, outputs, formatter and dev shell |
| `hosts/PC/` | Machine-specific hardware, boot, hostname, account and initial state version |
| `modules/nixos/` | Explicitly imported system features: base tools, development, GNOME, Mullvad VPN and Numtide cache |
| `home-manager/home.nix` | Standalone account profile and its explicit module imports |
| `home-manager/modules/` | User apps, GNOME inputs, browser, Git, MIME defaults, AI tools and SOPS integration |
| `scripts/`, `justfile`, `tests/` | Preview/switch guards, checks and mocked workflow tests |
| `secrets/` | Encrypted SOPS files only; decryption keys live outside this repo |

The host selects shared modules explicitly and keeps its hardware, boot policy,
hostname and `system.stateVersion` in `hosts/PC/`. The Home Manager profile
sets its own account and `home.stateVersion`; new user features belong in a
focused module imported from `home-manager/home.nix`.

## Workflow

Git flakes use tracked files as their source. Stage each new `.nix` file with
`git add` before checking or previewing; otherwise Nix will not see it.
The repo's `.gitignore` filters local build links and common plaintext
credential copies. The Home Manager Git module supplies a separate, narrow
global ignore for editor and OS leftovers; it does not hide `.env` files or
build output in unrelated repos. Neither layer hides Nix modules, `flake.lock`,
`.sops.yaml`, encrypted `secrets/*.yaml`, agent instructions, or documentation.
Ignore rules are not a secret scanner and do not hide files already tracked;
review `git diff --cached` before committing.

`just check` checks Nix file headers, evaluates both configurations, checks
explicit package lists for duplicates, and warns about untracked Nix files.
For individual checks, use `just headers`, `just verify` (flake evaluation), or
`just pkgs`. `just status` compares active, saved preview, and desired
generations without building or switching.

`justfile` drives the helpers in `scripts/`; `scripts/config.sh` centralizes
output selection and `scripts/saved-preview-build.sh` guards activation against
missing or stale previews. From the dev shell, `bash tests/workflow.sh` tests
those guards with temporary generations; it never activates a real one.

### Development tools

Development tools live only in the flake's dev shell, not in the installed
NixOS or Home Manager profiles. It uses the pinned Nixpkgs packages: the
[official nixfmt](https://github.com/NixOS/nixfmt) through `nixfmt-tree` for
Nix files, `shfmt` for shell scripts (2-space indentation), `statix` and
`deadnix` for Nix linting, and ShellCheck for shell linting. `just` formats its
own justfile. The shell also includes `sops` and `age` for encrypted secrets.
Formatting is opt-in; no background formatter or formatting hook runs.
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

### Selection and safety guards

The recipes select the output matching the running hostname and login when
possible, or a sole output. If selection is ambiguous, set `NIXOS_CONFIG`
and/or `HOME_CONFIG` to the intended flake output names. Activation still
checks that the selected NixOS hostname matches the running host and that the
Home Manager username and home directory match the caller.
Home-only recipes can select an explicit `HOME_CONFIG` without resolving any
NixOS output. When a caller needs both outputs, it selects the NixOS output
first and uses that host as context for Home selection.

`just build` builds the NixOS closure without activating it; `just preview`
builds it and diffs it against `/run/current-system`. `just home-preview`
builds the independent Home generation and shows its closure and managed-file
changes. Builds save `result-system` or `result-home` links under
`${XDG_STATE_HOME:-$HOME/.local/state}/nixos/`, outside the flake directory.
Both switches activate only the matching saved build; neither `check` nor
`status` activates anything. Unqualified `nixos-rebuild` uses `/etc/nixos`,
**not** this flake.

This host's rename from `nixos` to `PC` is migration history:
`ALLOW_HOST_RENAME=1` is only for a deliberately approved hostname change,
not a normal switch or a way to bypass a wrong output selection.

## Desktop and user applications

Home Manager is standalone and separate from the NixOS switch. Telegram,
Firefox, KeePassXC, GitHub CLI (`gh`), Wayland clipboard tools
(`wl-clipboard`), and the CLI tools in `home-manager/modules/cli.nix` are user
packages; NixOS provides Node.js/npm and pnpm for all users, including root.
Chrome, VS Code, and OBS Studio are also Home Manager packages; OBS has no
extra plugins. Nixcord manages Vesktop without installing Discord separately
or rebuilding the cached stock Vesktop package. Mullvad VPN is instead a
NixOS service with the GUI package; it does not declare auto-connect or extra
early-boot traffic blocking. Firefox remains the default browser for links.

### Firefox, GNOME and MIME defaults

Firefox declares Personal and Work with stable profile paths. Removing the old
Personal path override leaves that older profile on disk but selects a new
`personal` profile on the next Home Manager switch. Both profiles use DuckDuckGo
for normal and private search and have a few non-breaking privacy/comfort
preferences. Password databases, logins, and Firefox Sync remain unmanaged;
Home Manager does not manage your shell.

Run `just home-preview` to build and compare it with an existing Home Manager
profile, review managed home files, and see active and desired GNOME input
sources. Those sources are dconf settings, not managed files; GVariant type
annotations may make the two displayed values look different even when their
content agrees. No other dconf values or decrypted secrets are printed.
`just home-switch` runs without sudo. It verifies the selected user, home
directory, and saved build, then installs and activates that **exact** Home
Manager generation without another flake build.

`home-manager/modules/mime.nix` owns application defaults, including Firefox
web and Telegram URL associations. On this machine, the previous
`mimeapps.list`, Firefox `profiles.ini`, and Personal profile's
`search.json.mozlz4` were backed up under
`${XDG_STATE_HOME:-$HOME/.local/state}/nixos/firefox-mime-backup.*` before Home
Manager took ownership. Edit the modules rather than their managed symlinks.
KeePassXC's browser native-messaging host is installed, but its browser
extension and any password database are not configured.

## Git and signing

After a reviewed `just home-switch`, sign in interactively with `gh auth login`
and check with `gh auth status`. On Wayland, `wl-clipboard` lets `gh` copy the
one-time code; Firefox is the web URL handler in `home-manager/modules/mime.nix`.
To explicitly use Firefox for the login flow, run `GH_BROWSER=firefox gh auth login`
and press Enter at the URL prompt rather than clicking the terminal's hyperlink.
For HTTPS GitHub remotes, run `gh auth setup-git` after login to use `gh` as
Git's credential helper; for SSH remotes, register an SSH key with GitHub
instead. GitHub login data and credential-helper settings remain outside Home
Manager and the Nix store. Commits stay local until you explicitly push them.

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

## Encrypted user secrets

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
configuration have been migrated.** The example declaration does not activate
anything by itself.

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

## AI tools and caches

The AI module installs Codex CLI, Pi, OpenCode V2 (`opencode2`), Claude Code,
Antigravity CLI (`agy`), ChatGPT (the Linux desktop app also includes Codex),
Claude Desktop, Copilot CLI, T3Code Desktop, ZCode, `skills`, `ctx`, and
`executor` for the Home Manager user. Executor uses the pinned Numtide binary
package; no second input or package entry is needed.
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

Use `nix flake update mattPocockSkills` to update **only** that skills input to
a new upstream commit, then review the `flake.lock` diff and changed content. Run
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

## License

[WTFPL, version 2](LICENSE) — the same license used by
[gitanon](https://github.com/yzua/gitanon/blob/main/LICENSE).
