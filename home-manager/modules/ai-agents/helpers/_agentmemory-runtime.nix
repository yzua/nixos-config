{ pkgs }:

let
  iiiVersion = "0.11.2";
  iiiSrcBySystem = {
    x86_64-linux = pkgs.fetchurl {
      url = "https://github.com/iii-hq/iii/releases/download/iii/v${iiiVersion}/iii-x86_64-unknown-linux-gnu.tar.gz";
      hash = "sha256-nIPEd4i070vutl3ZvzfpT5k3cM09uHRGTDzhzckjUs0=";
    };
  };
in
{
  iiiEngine = pkgs.stdenvNoCC.mkDerivation {
    pname = "iii-engine";
    version = iiiVersion;

    src =
      iiiSrcBySystem.${pkgs.stdenv.hostPlatform.system}
        or (throw "agentmemory iii-engine is not packaged for ${pkgs.stdenv.hostPlatform.system}");

    dontConfigure = true;
    dontBuild = true;
    unpackPhase = ''
      runHook preUnpack
      tar -xzf "$src"
      runHook postUnpack
    '';

    installPhase = ''
      runHook preInstall
      mkdir -p "$out/bin"
      cp iii "$out/bin/iii"
      chmod +x "$out/bin/iii"
      runHook postInstall
    '';
  };
}
