set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
    @just --list

# Evaluate the flake without building or activating it.
verify:
    nix flake check --no-build --no-write-lock-file path:.

# Build a system closure without activating it.
build:
    mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/nixos"
    nix build --no-write-lock-file 'path:.#nixosConfigurations.nixos.config.system.build.toplevel' --out-link "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-system"

# Compare the built system with the one currently running.
preview: build
    nix store diff-closures /run/current-system "${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-system"

# Explicitly activate this host; run `just preview` and review the diff first.
switch:
    @test "$(hostname)" = "nixos" || { echo "This flake is for host nixos only" >&2; exit 1; }
    sudo nixos-rebuild switch --flake 'path:.#nixos' --no-write-lock-file --option experimental-features 'nix-command flakes'
