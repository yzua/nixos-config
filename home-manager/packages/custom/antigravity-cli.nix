# Antigravity CLI — terminal agent from Google Antigravity.

{
  pkgs,
  constants,
  ...
}:

let
  antigravityCli = pkgs.stdenvNoCC.mkDerivation rec {
    pname = "antigravity-cli";
    version = "1.0.1";
    releaseId = "5826024320139264";

    src = pkgs.fetchurl {
      url = "https://storage.googleapis.com/antigravity-public/antigravity-cli/${version}-${releaseId}/linux-x64/cli_linux_x64.tar.gz";
      hash = "sha512-vhF0oWXQa/Qf+3yxMAABRncfOEhrAFpopDxeYJH6gDIbOovNXTJeGJgftkiHC1lf9WMQgC1/kbsO2OdDJmhFOg==";
    };

    nativeBuildInputs = [ pkgs.autoPatchelfHook ];

    buildInputs = [ pkgs.stdenv.cc.cc.lib ];

    sourceRoot = ".";

    installPhase = ''
      runHook preInstall

      install -Dm755 antigravity "$out/bin/agy"

      runHook postInstall
    '';

    meta = with pkgs.lib; {
      description = "Terminal-first agent CLI from Google Antigravity";
      homepage = "https://github.com/google-antigravity/antigravity-cli";
      license = licenses.unfree;
      sourceProvenance = with sourceTypes; [ binaryNativeCode ];
      platforms = [ constants.system ];
      mainProgram = "agy";
    };
  };
in

{
  home.packages = [ antigravityCli ];
}
