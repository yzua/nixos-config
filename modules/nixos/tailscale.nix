# Personal Tailscale access for T3 Code without taking over work VPN routes or DNS.

{ config, ... }:

{
  services.tailscale = {
    enable = true;
    # Keep work split DNS, work routes, and Mullvad's default route in charge.
    # The NixOS firewall below handles incoming T3 Code traffic on tailscale0.
    extraSetFlags = [
      "--accept-dns=false"
      "--accept-routes=false"
      "--exit-node="
      "--netfilter-mode=off"
      "--ssh=false"
    ];
  };

  # T3 Code listens on port 3773 after Network access is enabled in the app.
  # Scope the exception to Tailscale, not the LAN or public interfaces.
  networking.firewall.interfaces.${config.services.tailscale.interfaceName}.allowedTCPPorts = [ 3773 ];
}
