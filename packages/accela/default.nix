# Wrap the verified ACCELA AppImage without running its upstream home installer.
{
  lib,
  appimageTools,
  fetchurl,
  dotnetCorePackages,
}:
let
  pname = "accela";
  version = "20260524150213";
  dotnet = dotnetCorePackages.runtime_9_0;
  src = fetchurl {
    name = "ACCELA.AppImage";
    url = "https://github.com/ciscosweater/enter-the-wired/releases/download/latest/deps.tar.gz";
    # Hash the extracted AppImage, not the mutable release tag or whole archive.
    hash = "sha256-Zu7ES0ecHIiUEcHZJZ+fBNqXIlz9BCBtWgmvBhd6eSY=";
    downloadToTemp = true;
    postFetch = ''
      tar -xf "$downloadedFile" bin/ACCELA.AppImage
      install -m 444 bin/ACCELA.AppImage "$out"
    '';
  };
  contents = appimageTools.extract { inherit pname version src; };
in
appimageTools.wrapType2 {
  inherit pname version src;
  extraPkgs = pkgs: [
    pkgs.icu
    pkgs.xcb-util-cursor
    pkgs.zstd
    dotnet
  ];
  extraProfile = ''
    export PATH="${dotnet}/bin:$PATH"
    export DOTNET_ROOT="${dotnet}/share/dotnet"
    export DOTNET_CLI_TELEMETRY_OPTOUT=1
  '';
  extraInstallCommands = ''
    install -Dm444 "${contents}/accela.png" "$out/share/pixmaps/accela.png"
    install -Dm444 "${contents}/ACCELA.desktop" "$out/share/applications/accela.desktop"
    substituteInPlace "$out/share/applications/accela.desktop" \
      --replace-fail 'Exec=run.sh' "Exec=$out/bin/accela %u"
  '';
  meta = {
    description = "ACCELA desktop companion for Enter The Wired";
    homepage = "https://github.com/ciscosweater/enter-the-wired";
    # The installer repo is MIT; the bundled application has no verified license.
    license = lib.licenses.unfree;
    platforms = [ "x86_64-linux" ];
    mainProgram = "accela";
  };
}
