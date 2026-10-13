# Pin published REA, its official skill and analysis engines without upstream installers.
{ pkgs }:
let
  # Runtime-only projection of the exact release lock; versions/integrities are unchanged.
  lock = builtins.fromJSON (builtins.readFile ./package-lock.json);
  cli = pkgs.stdenvNoCC.mkDerivation {
    pname = "rea-agents";
    version = "6.4.0";
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/rea-agents/-/rea-agents-6.4.0.tgz";
      hash = "sha512-Vj1zWfSlna5bphGoaoI/TcVBuYvze9u+OyPC3Shz8YkBqaCTqB4COnnRoX7XDwMpwI24ZlFEel2yEj0k8LTWEQ==";
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
      cp -r dist bridge scripts skills native third_party licenses package.json LICENSE "$out/lib/rea/"
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
  # REA 6.4.0 verifies this build and accepts the 12.1.x release line.
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
