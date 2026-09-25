set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
    @just --list

# Evaluate the flake without building or activating it.
verify:
    nix flake check --no-build --no-write-lock-file .

# Build a system closure without activating it.
build:
    mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/nixos"
    nix build --no-write-lock-file '.#nixosConfigurations.nixos.config.system.build.toplevel' --out-link "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-system"

# Compare the built system with the one currently running.
preview: build
    nix store diff-closures /run/current-system "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-system"

# Activate exactly the built closure; run `just preview` and review it first.
switch:
    @test "$(hostname)" = "nixos" || { echo "This flake is for host nixos only" >&2; exit 1; }
    @result="${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-system"; \
      test -L "$result" || { echo "No build found; run just preview first" >&2; exit 1; }; \
      expected="$(nix eval --raw --no-write-lock-file '.#nixosConfigurations.nixos.config.system.build.toplevel.outPath')"; \
      actual="$(readlink -f "$result")"; \
      test "$actual" = "$expected" || { echo "Build is stale; run just preview first" >&2; exit 1; }; \
      sudo nixos-rebuild switch --no-reexec --store-path "$actual"

# Build the independent Home Manager activation package without activating it.
home-build:
    mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/nixos"
    nix build --no-write-lock-file '.#homeConfigurations."yz@nixos".activationPackage' --out-link "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-home"

# Compare with a prior Home Manager profile if one exists.
home-preview: home-build
    @profile="${XDG_STATE_HOME:-$HOME/.local/state}/nix/profiles/home-manager"; \
      if [ -e "$profile" ]; then \
        nix store diff-closures "$profile" "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-home"; \
      else \
        echo "No prior Home Manager profile; this would be the first activation"; \
      fi
    @files="$(readlink -f "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-home/home-files")"; \
      profile="${XDG_STATE_HOME:-$HOME/.local/state}/nix/profiles/home-manager"; \
      old_files=""; \
      if [ -e "$profile/home-files" ]; then old_files="$(readlink -f "$profile/home-files")"; fi; \
      echo "Managed home files:"; \
      find "$files" -type l -printf '  ~/%P\n' | sort; \
      find "$files" -type l -printf '%P\n' | while IFS= read -r path; do \
        if [ -e "$HOME/$path" ] || [ -L "$HOME/$path" ]; then \
          if [ -z "$old_files" ] || [ ! -L "$HOME/$path" ] || \
             [ "$(readlink "$HOME/$path")" != "$old_files/$path" ]; then \
            echo "Already present (review before switching): ~/$path"; \
          fi; \
        fi; \
      done

# Explicitly activate this user's Home Manager config (never run with sudo).
home-switch:
    @test "$(id -un)" = "yz" || { echo "This home config is for yz only" >&2; exit 1; }
    @result="${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-home"; \
      test -L "$result" || { echo "No home build found; run just home-preview first" >&2; exit 1; }; \
      expected="$(nix eval --raw --no-write-lock-file '.#homeConfigurations."yz@nixos".activationPackage.outPath')"; \
      actual="$(readlink -f "$result")"; \
      test "$actual" = "$expected" || { echo "Home build is stale; run just home-preview first" >&2; exit 1; }; \
      nix develop . -c home-manager switch --flake '.#yz@nixos'
