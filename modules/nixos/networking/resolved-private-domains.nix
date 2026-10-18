# Resolve SOPS-selected domains through public DNS-over-TLS outside mesh DNS.

{
  config,
  ...
}:

let
  secret = "resolved-private-domains";
  dropInDir = "/etc/systemd/resolved.conf.d";
  # The drop-in must be a runtime-rendered file, not a store path, and its
  # directory a real directory that survives switches.
  dropIn = "${dropInDir}/60-${secret}.conf";
in
{
  assertions = [
    {
      assertion = config.services.resolved.enable;
      message = "Private domain overrides require services.resolved.enable.";
    }
  ];

  systemd.tmpfiles.rules = [ "d ${dropInDir} 0755 root root -" ];

  # Enable DNS-over-TLS for the "#"-suffixed global servers below. A policy
  # VPN blocks plaintext port 53 through its tunnel; opportunistic keeps the
  # plaintext fallback for link servers without TLS.
  services.resolved.settings.Resolve.DNSOverTLS = "opportunistic";

  sops.secrets.${secret} = {
    sopsFile = ../../../secrets/netbird-mullvad.yaml;
    key = "resolved_private_domains";
    mode = "0400";
  };

  sops.templates.${secret} = {
    path = dropIn;
    mode = "0644";
    restartUnits = [ "systemd-resolved.service" ];
    # The mesh DNS upstream becomes unreachable while a policy-routing VPN
    # tunnels its traffic, and mesh-cached answers expire. Selected domains
    # are public infrastructure, so resolve them directly. Keeping the list
    # SOPS-owned leaves no private hostnames in Git.
    content = ''
      [Resolve]
      DNS=1.1.1.1#cloudflare-dns.com 9.9.9.9#dns.quad9.net
      Domains=${config.sops.placeholder.${secret}}
    '';
  };
}
