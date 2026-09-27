# NetBird mesh VPN client and desktop UI.

{ setup, ... }:

{
  # Give the hardened NetBird daemon a split-DNS manager it can update.
  services.resolved.enable = true;

  services.netbird = {
    ui.enable = true;
    clients.default = {
      name = "netbird";
      port = 51820;
      interface = "wt0";
    };
  };

  # Allow the configured account to control the hardened daemon and use its UI.
  users.users.${setup.username}.extraGroups = [ "netbird" ];
}
