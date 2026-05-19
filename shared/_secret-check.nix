# Secret inventory check helper.
# Usage: import ./shared/_secret-check.nix { inherit lib; rootDir = ./.; }
# Returns { hasSecret : string -> bool; }

{ lib, rootDir }:

let
  secretFile = rootDir + "/secrets/secrets.yaml";
  secretFileText = lib.optionalString (builtins.pathExists secretFile) (
    "\n" + builtins.readFile secretFile
  );
in
{
  hasSecret = name: lib.hasInfix "\n${name}:" secretFileText;
}
