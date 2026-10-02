# Route the Tor daemon outside Mullvad's VPN tunnel on hosts that use both.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  # Mullvad's Linux split-tunnel marks; priority must stay between -200 and 0.
  # https://mullvad.net/en/help/split-tunneling-with-linux-advanced
  rules = pkgs.writeText "tor-mullvad-bypass.nft" ''
    table inet tor_mullvad_bypass
    delete table inet tor_mullvad_bypass
    table inet tor_mullvad_bypass {
      chain output {
        type route hook output priority -100; policy accept;
        meta skuid ${toString config.users.users.tor.uid} oifname != "lo" counter ct mark set 0x00000f41 meta mark set 0x6d6f6c65
      }
    }
  '';
in
{
  assertions = [
    {
      assertion = config.services.tor.enable;
      message = "Tor/Mullvad bypass requires services.tor.enable.";
    }
    {
      assertion = config.services.mullvad-vpn.enable;
      message = "Tor/Mullvad bypass requires services.mullvad-vpn.enable.";
    }
  ];

  # Gate the unit too, so missing prerequisites report assertions rather than
  # trying to evaluate the absent Tor user's UID while constructing the rule.
  # Fail Tor startup if the rule cannot load, without weakening its sandbox.
  systemd.services.tor-mullvad-bypass =
    lib.mkIf (config.services.tor.enable && config.services.mullvad-vpn.enable)
      {
        description = "Exclude the Tor daemon from Mullvad's VPN tunnel";
        before = [ "tor.service" ];
        requiredBy = [ "tor.service" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          ExecStart = "${pkgs.nftables}/bin/nft -f ${rules}";
          ExecStop = "${pkgs.nftables}/bin/nft delete table inet tor_mullvad_bypass";
        };
      };
}
