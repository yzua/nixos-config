# Pin published REA and its static-analysis engines without upstream installers.
{ pkgs }:
let
  # Runtime-only projection of the exact release lock; versions/integrities are unchanged.
  lock = builtins.fromJSON (builtins.readFile ./package-lock.json);
  cli = pkgs.stdenvNoCC.mkDerivation {
    pname = "rea-agents";
    version = "4.1.0";
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/rea-agents/-/rea-agents-4.1.0.tgz";
      hash = "sha512-BOig7QyPtOJLZtCa7MIVyecGdsI5C8kX0HHjp9Fo5LkotSqD3cRV91KCp0pakLqLuyF1BFl4RSyV/9F/Wk6OBQ==";
    };
    npmDeps = pkgs.importNpmLock {
      package = lock.packages."";
      packageLock = lock;
    };
    nativeBuildInputs = [
      pkgs.nodejs
      pkgs.importNpmLock.npmConfigHook
      pkgs.makeWrapper
      pkgs.autoPatchelfHook
    ];
    buildInputs = [ (pkgs.lib.getLib pkgs.stdenv.cc.cc) ];
    npmFlags = [ "--ignore-scripts" ];
    dontBuild = true;
    installPhase = ''
      runHook preInstall
      mkdir -p "$out/lib/rea" "$out/bin"
      cp -r dist bridge scripts skills package.json LICENSE "$out/lib/rea/"
      cp -r node_modules "$out/lib/rea/"
      # Unsupported Windows addon is not part of this Linux profile.
      makeWrapper ${pkgs.nodejs}/bin/node "$out/bin/rea" \
        --add-flags "$out/lib/rea/scripts/rea.mjs" \
        --set NO_UPDATE_NOTIFIER 1 \
        --prefix PATH : "${
          pkgs.lib.makeBinPath [
            pkgs.bash
            pkgs.coreutils
            pkgs.procps
          ]
        }"
      runHook postInstall
    '';
    meta = {
      description = "Pinned REA reverse-engineering CLI and MCP server";
      homepage = "https://github.com/morluto/rea";
      license = pkgs.lib.licenses.mit;
      platforms = [ "x86_64-linux" ];
      mainProgram = "rea";
    };
  };
  # REA 4.1.0's actual release probe requires this exact build, not stock 12.0.4.
  ghidra = pkgs.ghidra-bin.overrideAttrs (old: {
    version = "12.1.4";
    versiondate = "20260921";
    src = pkgs.fetchurl {
      url = "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip";
      hash = "sha256-3axJ+QPanVusgz5cx5OVCYucM8/TJ5vl8xvQA4fS1Ns=";
    };
    nativeBuildInputs = old.nativeBuildInputs ++ [ pkgs.unzip ];
  });
  jadxEngine = pkgs.fetchurl {
    url = "https://github.com/1013503897/jadx-headless-mcp/releases/download/v0.7.1/jadx-headless-mcp-0.7.1-all.jar";
    hash = "sha256-bl6s9QC2QpK/tzxJeXwZWPbuRGRuQ+hoA5rn/rVz/3U=";
  };
in
{
  inherit cli ghidra jadxEngine;
  jdk = pkgs.jdk21;
  packages = [
    cli
    ghidra
    pkgs.jdk21
  ];
}
