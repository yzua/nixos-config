#!/usr/bin/env bash
# Evaluate only package-list declarations from this flake, not packages added
# automatically by NixOS, GNOME, or Home Manager modules.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/config.sh
select_system
select_home

expr=$(
  cat <<'NIX'
let
  flake = builtins.getFlake (toString ./.);
  root = flake.outPath + "/";
  rootLength = builtins.stringLength root;

  declarations = scope: option:
    builtins.concatLists (map (definition:
      if builtins.substring 0 rootLength definition.file != root then []
      else map (package:
        builtins.concatStringsSep "\t" [
          scope
          "${package.pname or (builtins.parseDrvName package.name).name}:${package.outputName or "out"}"
          (builtins.substring rootLength (builtins.stringLength definition.file - rootLength) definition.file)
        ]) definition.value
    ) option.definitionsWithLocations);

  system = declarations "NixOS environment.systemPackages"
    flake.nixosConfigurations.${builtins.getEnv "NIXOS_CONFIG"}.options.environment.systemPackages;
  home = declarations "Home Manager home.packages"
    flake.homeConfigurations.${builtins.getEnv "HOME_CONFIG"}.options.home.packages;
in
builtins.concatStringsSep "\n" (system ++ home)
NIX
)

# --impure permits getFlake to resolve this local Git flake; the lock file is
# never written, and evaluation neither builds nor activates anything.
packages=$(nix eval --raw --impure --no-write-lock-file --expr "$expr")

if [[ -z "$packages" ]]; then
  echo "No packages declared in this repo's NixOS or Home Manager package lists."
  exit 0
fi

awk -F '\t' '
  {
    name = $2
    if (name in seen) {
      printf "Potential duplicate: %s\n  %s: %s\n  %s: %s\n", \
        name, firstScope[name], firstFile[name], $1, $3
      duplicates++
    } else {
      seen[name] = 1
      firstScope[name] = $1
      firstFile[name] = $3
    }
    count++
  }
  END {
    if (duplicates) {
      printf "Found %d repeated package declaration(s).\n", duplicates
      exit 1
    }
    printf "No duplicates in %d repo-declared packages (NixOS + Home Manager).\n", count
  }
' <<<"$packages"
