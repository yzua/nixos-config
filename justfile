set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
    @just --list

# Evaluate the flake without building or activating it.
verify:
    nix flake check --no-build --no-write-lock-file .

# Check headers, evaluate both configs, check packages, and flag untracked Nix files.
check:
    @untracked="$(git ls-files --others --exclude-standard -- '*.nix')"; \
      if [ -n "$untracked" ]; then \
        printf 'Warning: Git flakes ignore untracked .nix files. Stage new files you want evaluated:\n%s\n' "$untracked"; \
      else \
        echo "No untracked Nix files."; \
      fi
    @just headers
    @just verify
    @just pkgs

# Quickly flag Nix files that lack a purpose comment on the first line.
headers:
    @./scripts/check-nix-headers.sh

# Check for repeated packages in this repo's NixOS and Home Manager package lists.
pkgs:
    @./scripts/check-packages.sh

# Format Nix and shell files, then the command menu (explicitly modifies files).
fmt:
    nix fmt --no-write-lock-file
    just --fmt

# Read-only formatting check for Nix, shell, and the justfile.
fmt-check:
    @git ls-files -z --cached --others --exclude-standard -- '*.nix' ':(exclude)hardware-configuration.nix' ':(exclude,glob)**/hardware-configuration.nix' | xargs -0 -r -n1 nixfmt --check
    @git ls-files -z --cached --others --exclude-standard -- '*.sh' | xargs -0 -r shfmt -d -i 2
    just --fmt --check

# Fast static analysis; run in the dev shell if these tools are not installed.
lint: headers
    statix check --ignore 'hardware-configuration.nix' --ignore '**/hardware-configuration.nix' .
    @git ls-files -z --cached --others --exclude-standard -- '*.nix' ':(exclude)hardware-configuration.nix' ':(exclude,glob)**/hardware-configuration.nix' | xargs -0 -r deadnix --fail --
    @git ls-files -z --cached --others --exclude-standard -- '*.sh' | xargs -0 -r shellcheck -x

# Show the desired, saved preview, and active system/home generations (no build or switch).
status:
    @./scripts/status.sh

# Build a system closure without activating it.
build:
    mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/nixos"
    @source scripts/config.sh; select_system; \
      nix build --no-write-lock-file "$system_ref.config.system.build.toplevel" --out-link "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-system"

# Compare the built system with the one currently running.
preview: build
    nix store diff-closures /run/current-system "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-system"

# Activate exactly the built closure; run `just preview` and review it first.
switch:
    @source scripts/config.sh; source scripts/saved-preview-build.sh; select_system; \
      configured_host="$(nix eval --raw --no-write-lock-file "$system_ref.config.networking.hostName")"; \
      current_host="$(hostname)"; \
      test -n "$configured_host" || { echo 'The selected NixOS configuration has no hostname' >&2; exit 1; }; \
      if [ "$current_host" != "$configured_host" ]; then \
        test "${ALLOW_HOST_RENAME:-}" = 1 || { \
          printf 'Host mismatch: running %s, selected %s (%s). To deliberately rename this host, use ALLOW_HOST_RENAME=1 just switch.\n' "$current_host" "$configured_host" "$NIXOS_CONFIG" >&2; exit 1; \
        }; \
        printf 'Opted in to hostname change: %s -> %s\n' "$current_host" "$configured_host"; \
      fi; \
      result="${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-system"; \
      actual="$(require_saved_preview_build "$system_ref.config.system.build.toplevel.outPath" "$result" preview)"; \
      sudo nixos-rebuild switch --no-reexec --store-path "$actual"

# Build the independent Home Manager activation package without activating it.
home-build:
    mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/nixos"
    @source scripts/config.sh; select_home; \
      nix build --no-write-lock-file "$home_ref.activationPackage" --out-link "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-home"

# Compare with a prior Home Manager profile if one exists.
home-preview: home-build
    @./scripts/home-preview.sh

# Explicitly activate this user's Home Manager config (never run with sudo).
home-switch:
    @./scripts/home-switch.sh
