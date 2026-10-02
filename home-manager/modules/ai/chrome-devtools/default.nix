# Install pinned Chrome DevTools CLI/MCP commands with NixOS browser discovery.

{ pkgs, ... }:

let
  src = ./.;
  chromeDevtools = pkgs.stdenvNoCC.mkDerivation (finalAttrs: {
    pname = "pnpm-global-tools";
    version = "1";
    inherit src;

    pnpmDeps = pkgs.fetchPnpmDeps {
      inherit (finalAttrs) pname version src;
      inherit (pkgs) pnpm;
      fetcherVersion = 4;
      hash = "sha256-RvmV2bz7c7BgNEFxsK5TK3QCL654AZbsAj+rWm5zxqY=";
    };

    nativeBuildInputs = [
      pkgs.makeWrapper
      pkgs.nodejs
      pkgs.pnpm
      pkgs.pnpmConfigHook
    ];

    dontBuild = true;
    installPhase = ''
      runHook preInstall
      substituteInPlace node_modules/chrome-devtools-mcp/build/src/config/mcp-options.js \
        --replace-fail "args.channel = 'stable';" \
        "args.executablePath = '${pkgs.google-chrome}/bin/google-chrome-stable';"
      mkdir -p "$out/bin" "$out/lib/pnpm-global-tools"
      cp -r node_modules "$out/lib/pnpm-global-tools/"
      for bin in "$out/lib/pnpm-global-tools/node_modules/.bin/"*; do
        [ -f "$bin" ] || continue
        makeWrapper "$bin" "$out/bin/$(basename "$bin")" \
          --prefix PATH : "${pkgs.nodejs}/bin"
      done
      test -x "$out/bin/chrome-devtools"
      runHook postInstall
    '';
  });
in
{
  home.packages = [ chromeDevtools ];
}
