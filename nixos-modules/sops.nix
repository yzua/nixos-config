# SOPS-Nix encrypted secrets management (age encryption).

{
  config,
  constants,
  inputs,
  lib,
  user,
  ...
}:

let
  mkUserSecret = _: {
    owner = user;
    mode = "0400";
  };
in
{
  imports = [ inputs.sops-nix.nixosModules.sops ];

  sops = {
    defaultSopsFile = ../secrets/secrets.yaml;
    defaultSopsFormat = "yaml";
    validateSopsFiles = true;

    age = {
      keyFile = "/home/${user}/${constants.paths.sopsKeyDir}";
      generateKey = false;
    };

    secrets =
      (builtins.listToAttrs (
        map
          (name: {
            inherit name;
            value = mkUserSecret name;
          })
          [
            "zai_api_key"
            "openrouter_api_key"
            "context7_api_key"
            "gemini_api_key"
          ]
      ))
      // lib.optionalAttrs config.mySystem.observability.enable {
        grafana_admin_password = {
          owner = "grafana";
          mode = "0400";
        };
      }
      // {
        ntfy_topic = {
          mode = "0444"; # DynamicUser service — no persistent user/group to grant access
        };
        noctalia_location = {
          owner = user;
          mode = "0444";
        };
      };

    # SOPS templates: generate config files with secret interpolation.
    # Templates are rendered at activation time (not in the Nix store),
    # so secrets never appear in /nix/store. The rendered file is placed
    # at the specified path with the specified owner/mode.
    templates = {
      "ai-api-keys.env" = {
        owner = user;
        mode = "0400";
        content = ''
          ZAI_API_KEY=${config.sops.placeholder.zai_api_key}
          OPENROUTER_API_KEY=${config.sops.placeholder.openrouter_api_key}
          CONTEXT7_API_KEY=${config.sops.placeholder.context7_api_key}
          GEMINI_API_KEY=${config.sops.placeholder.gemini_api_key}
        '';
      };
    };
  };
}
