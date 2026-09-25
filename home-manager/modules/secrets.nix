# Configure the user's SOPS age key path; private keys stay outside the Nix store.

{ config, ... }:

{
  # This identity is installed separately from the flake and never copied into
  # the Nix store. Declare secrets where they are consumed, with a sopsFile.
  sops.age.keyFile = "${config.xdg.configHome}/sops/age/keys.txt";

  # Harmless end-to-end smoke test; no application consumes this secret.
  sops.secrets.test.sopsFile = ../../secrets/test.yaml;
}
