# Install pinned Chrome DevTools CLI/MCP commands with NixOS browser discovery.

{ pkgs, ... }:

let
  src = ./.;
  chromeDevtools = pkgs.stdenvNoCC.mkDerivation (finalAttrs: {
    pname = "chrome-devtools-mcp";
    version = (builtins.fromJSON (builtins.readFile ./package.json)).dependencies.chrome-devtools-mcp;
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
      mkdir -p "$out/bin" "$out/lib/${finalAttrs.pname}"
      cp -r node_modules "$out/lib/${finalAttrs.pname}/"
      for bin in "$out/lib/${finalAttrs.pname}/node_modules/.bin/"*; do
        [ -f "$bin" ] || continue
        makeWrapper "$bin" "$out/bin/$(basename "$bin")" \
          --prefix PATH : "${pkgs.nodejs}/bin"
      done
      test -x "$out/bin/chrome-devtools"
      test -x "$out/bin/chrome-devtools-mcp"
      runHook postInstall
    '';
  });
in
{
  home.packages = [ chromeDevtools ];
}
