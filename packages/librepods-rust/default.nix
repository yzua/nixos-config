# Package the official Rust LibrePods client with its desktop assets and runtime libraries.
{
  lib,
  rustPlatform,
  fetchFromGitHub,
  pkg-config,
  makeBinaryWrapper,
  desktop-file-utils,
  systemd,
  dbus,
  libpulseaudio,
  alsa-lib,
  bluez,
  expat,
  fontconfig,
  freetype,
  libGL,
  libX11,
  libXcursor,
  libXi,
  libXrandr,
  wayland,
  libxkbcommon,
  vulkan-loader,
}:
let
  runtimeLibraries = [
    dbus
    libpulseaudio
    alsa-lib
    bluez
    expat
    fontconfig
    freetype
    libGL
    libX11
    libXcursor
    libXi
    libXrandr
    wayland
    libxkbcommon
    vulkan-loader
  ];
in
rustPlatform.buildRustPackage {
  pname = "librepods-rust";
  version = "0.1.0-unstable-2026-05-15";

  src = fetchFromGitHub {
    owner = "librepods-org";
    repo = "librepods";
    rev = "672e65ad36eebf21ff1c1a508066f9197ee56d17";
    hash = "sha256-EuIYvBqBtpgutVqPOLIO3E9OhVzQ5q5TDoz/F+9MHEE=";
  };

  sourceRoot = "source/linux-rust";
  cargoHash = "sha256-17dE+oYvECU4f1SL6LHS95sXEea/Z0VgTPQ4u6TZTic=";

  nativeBuildInputs = [
    pkg-config
    makeBinaryWrapper
    desktop-file-utils
  ];
  buildInputs = runtimeLibraries;

  # Keep upstream source unchanged; this pin has no unit tests.
  doCheck = false;

  postInstall = ''
    install -Dm644 assets/me.kavishdevar.librepods.desktop \
      "$out/share/applications/me.kavishdevar.librepods.desktop"
    install -Dm644 assets/icon.png \
      "$out/share/icons/hicolor/256x256/apps/me.kavishdevar.librepods.png"

    # Keep the ELF at a stable path for a separately configured capability wrapper.
    # This package itself neither grants capabilities nor changes host services.
    mkdir -p "$out/libexec"
    mv "$out/bin/librepods" "$out/libexec/librepods"
    # Ambient Bluetooth capabilities must never enter a shell interpreter.
    # Fix runtime paths too: upstream launches bluetoothctl and systemctl.
    makeBinaryWrapper "$out/libexec/librepods" "$out/bin/librepods" \
      --set LD_LIBRARY_PATH ${lib.makeLibraryPath runtimeLibraries} \
      --set PATH ${
        lib.makeBinPath [
          bluez
          systemd
        ]
      } \
      --unset BASH_ENV --unset ENV
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    desktop-file-validate "$out/share/applications/me.kavishdevar.librepods.desktop"
    env -u DISPLAY -u WAYLAND_DISPLAY "$out/bin/librepods" --help
    env -u DISPLAY -u WAYLAND_DISPLAY "$out/bin/librepods" --version
    runHook postInstallCheck
  '';

  meta = {
    description = "AirPods liberated from Apple's ecosystem (Rust client)";
    homepage = "https://github.com/librepods-org/librepods";
    license = lib.licenses.gpl3Only;
    platforms = lib.platforms.linux;
    mainProgram = "librepods";
  };
}
