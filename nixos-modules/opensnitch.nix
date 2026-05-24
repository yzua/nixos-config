# OpenSnitch application firewall with per-app network logging.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  mkAllowRule = name: operator: {
    inherit name operator;
    enabled = true;
    action = "allow";
    duration = "always";
    precedence = true;
    nolog = false;
  };

  allowPath =
    name: path:
    mkAllowRule name {
      type = "simple";
      sensitive = false;
      operand = "process.path";
      data = path;
    };

  allowPathRegex =
    name: pattern:
    mkAllowRule name {
      type = "regexp";
      sensitive = false;
      operand = "process.path";
      data = pattern;
    };
in
{
  options.mySystem.opensnitch = {
    enable = lib.mkEnableOption "OpenSnitch application firewall with per-app network logging";
  };

  config = lib.mkIf config.mySystem.opensnitch.enable {
    mySystem.systemReport.features.HAS_OPENSNITCH = lib.boolToString true;
    services.opensnitch = {
      enable = true;

      settings = {
        DefaultAction = "deny"; # Block all unknown outbound connections
        DefaultDuration = "always";
        ProcMonitorMethod = "ebpf";
        Firewall = "nftables";
        LogLevel = 1; # warning
      };

      rules = {
        mullvad-daemon = allowPath "mullvad-daemon" "${pkgs.mullvad-vpn}/bin/mullvad-daemon";
        dnscrypt-proxy = allowPath "dnscrypt-proxy" "${pkgs.dnscrypt-proxy}/bin/dnscrypt-proxy";
        tor = allowPath "tor" "${pkgs.tor}/bin/tor";
        i2pd = allowPath "i2pd" "${pkgs.i2pd}/bin/i2pd";
        yggdrasil = allowPath "yggdrasil" "${pkgs.yggdrasil}/bin/yggdrasil";

        nix-tools = allowPathRegex "nix-tools" "^/nix/store/[^/]+-nix-[^/]+/bin/(nix|nix-daemon)$";
        browsers = allowPathRegex "browsers" "^/nix/store/[^/]+-(brave|chromium|librewolf|firefox|google-chrome|ungoogled-chromium)[^/]*/bin/.*";
        dev-tools = allowPathRegex "dev-tools" "^/nix/store/[^/]+-(git|curl|wget|openssh|gh|go|nodejs|python3|uv|cargo|rustup)[^/]*/bin/.*";
        ai-cli-tools = allowPathRegex "ai-cli-tools" "^/nix/store/[^/]+-(codex|claude|opencode|antigravity|nodejs|bun)[^/]*/bin/.*";
      };
    };
  };
}
