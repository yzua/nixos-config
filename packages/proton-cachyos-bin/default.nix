# Official prebuilt Proton-CachyOS runner for Steam's Linux Runtime.
{
  lib,
  stdenvNoCC,
  fetchurl,
}:

stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "proton-cachyos-bin";
  version = "11.0-20261015";

  src = fetchurl {
    url = "https://github.com/CachyOS/proton-cachyos/releases/download/cachyos-${finalAttrs.version}-slr/proton-cachyos-${finalAttrs.version}-slr-x86_64.tar.xz";
    hash = "sha256-NeFuq2NnJOPteqji28M+uOEC4MY7vCi1o5r1RMddW9M=";
  };

  outputs = [
    "out"
    "steamcompattool"
  ];

  dontConfigure = true;
  dontBuild = true;
  # Steam's container provides the runtime; preserve upstream binaries/scripts.
  dontFixup = true;

  installPhase = ''
    runHook preInstall

    echo 'Use programs.steam.extraCompatPackages, not environment.systemPackages.' > "$out"
    mkdir -p "$steamcompattool"
    cp -a ./. "$steamcompattool/"

    # Match upstream's SLR packaging, with a stable tool ID and relative path.
    cat > "$steamcompattool/compatibilitytool.vdf" <<EOF
    "compatibilitytools"
    {
      "compat_tools"
      {
        "proton-cachyos-slr"
        {
          "install_path" "."
          "display_name" "Proton-CachyOS ${finalAttrs.version} (Steam Linux Runtime)"
          "from_oslist" "windows"
          "to_oslist" "linux"
        }
      }
    }
    EOF

    runHook postInstall
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    test -x "$steamcompattool/proton"
    test -s "$steamcompattool/toolmanifest.vdf"
    test -s "$steamcompattool/compatibilitytool.vdf"
    test -s "$steamcompattool/LICENSE"
    runHook postInstallCheck
  '';

  meta = {
    description = "Proton-CachyOS Steam compatibility tool (prebuilt Linux Runtime edition)";
    homepage = "https://github.com/CachyOS/proton-cachyos";
    # Proton's top level is BSD-3-Clause; bundled components retain their licenses.
    license = with lib.licenses; [
      bsd3
      lgpl21Plus
      zlib
      mit
      mpl20
    ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
    platforms = [ "x86_64-linux" ];
  };
})
