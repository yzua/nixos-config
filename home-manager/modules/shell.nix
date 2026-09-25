# Interactive Bash and opt-in project environment integrations.

{
  programs.bash = {
    enable = true;
    # Bash is supplied by NixOS; Home Manager only owns its user configuration.
    package = null;
  };

  programs.fzf = {
    enable = true;
    enableBashIntegration = true;
  };

  programs.zoxide = {
    enable = true;
    enableBashIntegration = true;
  };

  # direnv runs only for projects whose .envrc has been explicitly allowed.
  programs.direnv = {
    enable = true;
    enableBashIntegration = true;
    nix-direnv.enable = true;
  };
}
