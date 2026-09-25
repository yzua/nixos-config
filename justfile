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
      sudo nixos-rebuild switch --store-path "$actual"
