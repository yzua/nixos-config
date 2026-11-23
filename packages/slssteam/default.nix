# Build the pinned SLSsteam audit library without running its mutable installer.
{
  lib,
  pkgs,
  fetchFromGitHub,
}:
let
  # First release built for Steam's 64-bit client; 32-bit builds cannot load there.
  rev = "4dec48344c51c8180a23d914e5522a9ab0ed70f5";
in
# Follow upstream's nix-modules/default.nix while using this repository's pin.
pkgs.stdenv.mkDerivation {
  pname = "slssteam";
  version = "20261112130346";
  src = fetchFromGitHub {
    owner = "AceSLS";
    repo = "SLSsteam";
    inherit rev;
    hash = "sha256-lNs5Vm8eR3+10Jt4V/8J2y/InWnlqXCfnWAn0uNjOKY=";
  };

  env.GIT_COMMIT_HASH = rev;
  nativeBuildInputs = [
    pkgs.pkg-config
    pkgs.patchelf
  ];
  buildInputs = with pkgs; [
    curl
    dbus
    luajit
  ];

  postPatch = ''
    patchShebangs embed-version.sh embed-config.sh
  '';
  buildPhase = ''
    runHook preBuild
    make clean
    make audit-libs JOBS="$NIX_BUILD_CORES"
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm555 bin/SLSsteam.so "$out/SLSsteam.so"
    install -Dm444 res/config.yaml "$out/share/SLSsteam/config.yaml"
    substituteInPlace "$out/share/SLSsteam/config.yaml" \
      --replace-fail 'SafeMode: no' 'SafeMode: yes'
    runHook postInstall
  '';
  postFixup = ''
    patchelf --remove-rpath "$out/SLSsteam.so"
  '';

  meta = {
    description = "Steam client modification for Linux";
    homepage = "https://github.com/AceSLS/SLSsteam";
    license = lib.licenses.agpl3Only;
    platforms = [ "x86_64-linux" ];
  };
}
