# Personal Tailscale client that preserves existing VPN routes and DNS.

{
  services.tailscale = {
    enable = true;
    # Keep other VPNs' DNS and routes in charge; let NixOS own the firewall.
    extraSetFlags = [
      "--accept-dns=false"
      "--accept-routes=false"
      "--exit-node="
      "--netfilter-mode=off"
      "--ssh=false"
    ];
  };
}
