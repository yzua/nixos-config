set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
    @just --list

# Evaluate the flake without building or activating it.
verify:
    nix flake check --no-build --no-write-lock-file .

# Evaluate both configs and flag Nix files Git flakes cannot see yet.
check:
    @untracked="$(git ls-files --others --exclude-standard -- '*.nix')"; \
      if [ -n "$untracked" ]; then \
        printf 'Warning: Git flakes ignore untracked .nix files. Stage new files you want evaluated:\n%s\n' "$untracked"; \
      else \
        echo "No untracked Nix files."; \
      fi
    @just verify

# Format Nix and shell files, then the command menu (explicitly modifies files).
fmt:
    nix fmt --no-write-lock-file
    just --fmt

# Read-only formatting check for Nix, shell, and the justfile.
fmt-check:
    @git ls-files -z --cached --others --exclude-standard -- '*.nix' ':(exclude)hardware-configuration.nix' ':(exclude,glob)**/hardware-configuration.nix' | \
      while IFS= read -r -d '' file; do if [ -f "$file" ]; then nixfmt --check "$file"; fi; done
    @git ls-files -z --cached --others --exclude-standard -- '*.sh' | \
      while IFS= read -r -d '' file; do if [ -f "$file" ]; then shfmt -d -i 2 "$file"; fi; done
    just --fmt --check

# Fast static analysis; run in the dev shell if these tools are not installed.
lint:
    statix check --ignore 'hardware-configuration.nix' --ignore '**/hardware-configuration.nix' .
    @git ls-files -z --cached --others --exclude-standard -- '*.nix' ':(exclude)hardware-configuration.nix' ':(exclude,glob)**/hardware-configuration.nix' | \
      while IFS= read -r -d '' file; do if [ -f "$file" ]; then deadnix --fail -- "$file"; fi; done
    @git ls-files -z --cached --others --exclude-standard -- '*.sh' | \
      while IFS= read -r -d '' file; do if [ -f "$file" ]; then shellcheck -x "$file"; fi; done

# Show the desired, saved preview, and active system/home generations (no build or switch).
status:
    @./scripts/status.sh

# Build and compare the system, then save the reviewed generation.
preview:
    @source scripts/config.sh; source scripts/saved-preview-build.sh; select_system; \
      actual="$(nix build --no-write-lock-file --no-link --print-out-paths "$system_ref.config.system.build.toplevel")"; \
      nix store diff-closures /run/current-system "$actual"; \
      result="$(saved_preview_link system "$NIXOS_CONFIG")"; \
      mkdir -p "$(dirname "$result")"; \
      ln -sfnT "$actual" "$result"

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
      result="$(saved_preview_link system "$NIXOS_CONFIG")"; \
      actual="$(require_saved_preview_build "$system_ref.config.system.build.toplevel.outPath" "$result" preview)"; \
      sudo nixos-rebuild switch --no-reexec --store-path "$actual"

# Build and compare Home Manager, then save the reviewed generation.
home-preview:
    @./scripts/home-preview.sh

# Explicitly activate this user's Home Manager config (never run with sudo).
home-switch:
    @./scripts/home-switch.sh
