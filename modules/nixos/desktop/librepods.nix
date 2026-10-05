# Install pinned Rust LibrePods with Bluetooth capability access restricted to its user group.

{
  lib,
  librepodsPackage,
  setup,
  ...
}:

{
  # LibrePods needs CAP_NET_ADMIN for its low-level Bluetooth control sockets.
  # Keep the privileged entry point in NixOS, not a user-owned setcap binary.
  environment.systemPackages = [ librepodsPackage ];
  users.groups.librepods = { };
  users.users.${setup.username}.extraGroups = [ "librepods" ];

  security.wrappers.librepods = {
    source = lib.getExe librepodsPackage;
    capabilities = "cap_net_admin+ep";
    owner = "root";
    group = "librepods";
    permissions = "u+rx,g+x";
  };
}
