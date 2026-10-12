# Decrypt root-owned SOPS runtime secrets with the existing workstation age identity.

{ setup, ... }:

{
  # Read the existing protected key in place; never copy it into the Nix store.
  sops.age.keyFile = "${setup.homeDirectory}/.config/sops/age/keys.txt";
  sops.age.sshKeyPaths = [ ];
  sops.gnupg.sshKeyPaths = [ ];
  # A real unit supplies mount ordering for the existing home-based identity.
  sops.useSystemdActivation = true;
}
