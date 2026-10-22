# Build pinned SLSsteam audit libraries without running its mutable installer.
{
  lib,
  pkgs,
  fetchFromGitHub,
}:
let
  rev = "a45c19b989bef0295a8e717e2bfd8e2bbf3ad40d";
in
# Follow upstream's nix-modules/default.nix, including its bundled static
# dependencies, while using this repository's existing Nixpkgs pin.
pkgs.pkgsi686Linux.stdenv.mkDerivation {
  pname = "slssteam";
  version = "20261014151919";
  src = fetchFromGitHub {
    owner = "AceSLS";
    repo = "SLSsteam";
    inherit rev;
    hash = "sha256-iFKMZJiDCWri3LfJE3uCQU9NJJuaoUHCQmC6A+Hz/GA=";
  };

  env.GIT_COMMIT_HASH = rev;
  nativeBuildInputs = [ pkgs.pkg-config ];
  buildInputs = with pkgs.pkgsi686Linux; [
    openssl
    curl
    luajit
  ];

  postPatch = ''
    substituteInPlace src/log.cpp \
      --replace-fail "notify-send" "${lib.getExe pkgs.libnotify}"
    patchShebangs embed-version.sh embed-config.sh
  '';
  buildPhase = ''
    runHook preBuild
    make audit-libs JOBS="$NIX_BUILD_CORES"
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm555 bin/SLSsteam.so "$out/SLSsteam.so"
    install -Dm555 bin/library-inject.so "$out/library-inject.so"
    install -Dm444 res/config.yaml "$out/share/SLSsteam/config.yaml"
    substituteInPlace "$out/share/SLSsteam/config.yaml" \
      --replace-fail 'SafeMode: no' 'SafeMode: yes'
    runHook postInstall
  '';

  meta = {
    description = "Steam client modification for Linux";
    homepage = "https://github.com/AceSLS/SLSsteam";
    license = lib.licenses.agpl3Only;
    platforms = [ "i686-linux" ];
  };
}
