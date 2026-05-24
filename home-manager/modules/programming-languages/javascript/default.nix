# JavaScript/TypeScript development environment (Node, Bun, Deno, LSP, etc).

{
  config,
  lib,
  pkgs,
  ...
}:

let
  mkShellAliasPrograms = import ../../../_helpers/_shell-alias-programs.nix;
  bunGlobalPackages = [
    "@anthropic-ai/claude-code"
    "@oh-my-pi/pi-coding-agent"
    "@openai/codex"
    "opencode-ai"
    "skills"
    "agent-browser"
    "agent-device"
    "@playwright/cli"
  ];
  homeDir = config.home.homeDirectory;
  npmGlobalDir = "${homeDir}/.npm-global";
  pnpmHomeDir = "${homeDir}/.local/share/pnpm";
  bunInstallDir = "${homeDir}/.bun";
  cacertDir = "${pkgs.cacert}/etc/ssl/certs";
  cacertBundle = "${cacertDir}/ca-bundle.crt";
in
{
  programs =
    let
      shellAliases = {
        tscl = "tsc --noEmit";
        tscw = "tsc --watch";
        tscb = "tsc --build";
        el = "eslint --fix";
        pf = "prettier --write";
        jt = "jest --watch";
        vt = "npx vitest";
        pt = "npx playwright";
        bc = "biome check";
        bf = "biome format";
        bcf = "biome check --apply";
        blint = "biome lint";
        bfmt = "biome format --write";
      };
    in
    (mkShellAliasPrograms { inherit shellAliases; })
    // {
      git.ignores = import ./_gitignores.nix;
    };

  home = {
    # Wrapper sets system Chromium path before every playwright-cli invocation.
    # ~/.local/bin (pos 3 in PATH) takes priority over ~/.bun/bin (pos 6),
    # so this intercepts all calls regardless of env var inheritance.
    file.".local/bin/playwright-cli" = {
      executable = true;
      text = builtins.readFile ../../../../scripts/apps/playwright-cli-mcp-wrapper.sh;
    };

    packages = with pkgs; [
      nodejs
      bun
      deno
      pnpm
      yarn
      typescript-language-server
      vscode-langservers-extracted
      emmet-language-server
      tailwindcss-language-server
      eslint
      prettier
      stylelint
      eslint_d
      biome
      esbuild
      swc
      live-server
      http-server
      np
      commitizen
      prisma
      graphql-language-service-cli
      netlify-cli
      supabase-cli
      dockerfile-language-server
    ];

    sessionVariables = {
      NODE_ENV = "development";
      NPM_CONFIG_PREFIX = npmGlobalDir;
      PNPM_HOME = pnpmHomeDir;
      BUN_INSTALL = bunInstallDir;
      SSL_CERT_DIR = cacertDir;
      SSL_CERT_FILE = cacertBundle;
      NODE_EXTRA_CA_CERTS = cacertBundle;
      COREPACK_ENABLE_AUTO_PIN = "1";
      COREPACK_DEFAULT_TO_LATEST = "0";
    };

    sessionPath = [
      "${npmGlobalDir}/bin"
      "${bunInstallDir}/bin"
      "${homeDir}/.cache/.bun/bin"
      pnpmHomeDir
      "${homeDir}/.deno/bin"
    ];

    activation.createJSWorkspace = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      $DRY_RUN_CMD mkdir -p $HOME/Projects/{javascript,typescript,react,node}
      $DRY_RUN_CMD mkdir -p $HOME/.npm-global

      $DRY_RUN_CMD ${pkgs.nodejs}/bin/npm config set prefix "$HOME/.npm-global"

      echo "📦 Managing global JS packages with bun..."
      $DRY_RUN_CMD ${pkgs.bun}/bin/bun add --global --cwd "$HOME" --no-summary ${lib.escapeShellArgs bunGlobalPackages} || echo "❌ Failed to manage Bun global packages"

      # Remove Bun's t3 shim so the npm-managed binary can take precedence cleanly.
      $DRY_RUN_CMD ${pkgs.bun}/bin/bun remove --global --cwd "$HOME" t3 >/dev/null 2>&1 || true
      # Remove retired standalone Gemini CLI; Antigravity CLI is Nix-managed as agy.
      $DRY_RUN_CMD ${pkgs.bun}/bin/bun remove --global --cwd "$HOME" @google/gemini-cli >/dev/null 2>&1 || true
      $DRY_RUN_CMD ${pkgs.nodejs}/bin/npm uninstall --global @google/gemini-cli >/dev/null 2>&1 || true
      $DRY_RUN_CMD rm -f "$HOME/.npm-global/bin/gemini" "$HOME/.npm-global/bin/gemini-cli"

      echo "✔ Global packages management completed"
    '';
  };
}
