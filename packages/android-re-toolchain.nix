# Pin the rooted-emulator lab's SDK, static tools, device CLI and Frida artifacts.
{ pkgs, androidLab }:
let
  sdk =
    (pkgs.androidenv.composeAndroidPackages {
      cmdLineToolsVersion = "20.0";
      toolsVersion = null;
      platformToolsVersion = "37.0.0";
      buildToolsVersions = [ "35.0.0" ];
      includeEmulator = true;
      emulatorVersion = "36.5.11";
      platformVersions = [ androidLab.apiLevel ];
      includeSystemImages = true;
      systemImageTypes = [ androidLab.imageType ];
      abiVersions = [ androidLab.abi ];
      includeSources = false;
      includeCmake = false;
      includeNDK = false;
      includeExtras = [ ];
    }).androidsdk;
  fridaVersion = pkgs.python3Packages.frida-python.version;
  # This artifact was checked against the official release's SHA-256 digest.
  fridaServer =
    assert fridaVersion == "17.5.1" && androidLab.abi == "x86_64";
    pkgs.stdenvNoCC.mkDerivation {
      pname = "pi-re-frida-server-android-x86_64";
      version = fridaVersion;
      src = pkgs.fetchurl {
        url = "https://github.com/frida/frida/releases/download/17.5.1/frida-server-17.5.1-android-x86_64.xz";
        hash = "sha256-Gaia11w0Gr/7CJufaOLMDDQLItIFA/Wg+cFzf1gDRN8=";
      };
      nativeBuildInputs = [ pkgs.xz ];
      dontUnpack = true;
      dontBuild = true;
      dontFixup = true;
      installPhase = ''
        mkdir -p "$out/share/pi-re"
        xz -dc "$src" > "$out/share/pi-re/frida-server"
        chmod 755 "$out/share/pi-re/frida-server"
      '';
      meta = {
        description = "Official matched Frida server for the Android x86_64 lab";
        license = with pkgs.lib.licenses; [
          lgpl2Plus
          wxWindowsException31
        ];
        platforms = [ "x86_64-linux" ];
      };
    };
  agentDevice = pkgs.stdenvNoCC.mkDerivation {
    pname = "pi-re-agent-device";
    version = "0.21.18";
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/agent-device/-/agent-device-0.21.18.tgz";
      hash = "sha512-ptNJ7a4jkAXFLSmZqKJDwxL+YpCEUuZv3oCBY76PwE3b2W+yQqQuG0ej0/bOspIHJRmMGNOkWhtxm3gmRW9hRQ==";
    };
    nativeBuildInputs = [ pkgs.makeWrapper ];
    dontBuild = true;
    installPhase = ''
      mkdir -p "$out/lib/agent-device" "$out/bin"
      cp -r . "$out/lib/agent-device/"
      # Upstream's absolute /bin/ps is absent on NixOS. Keep its recorded-start
      # identity and safe-stop checks intact, using the pinned procps executable.
      substituteInPlace "$out/lib/agent-device/dist/src/owner-identity.js" \
        --replace-fail '/bin/ps' '${pkgs.procps}/bin/ps'
      test -f "$out/lib/agent-device/android/snapshot-helper/dist/agent-device-android-snapshot-helper.apk" || \
        find "$out/lib/agent-device/android/snapshot-helper/dist" -name '*.apk' -print -quit | grep -q .
      makeWrapper ${pkgs.nodejs}/bin/node "$out/bin/agent-device" \
        --add-flags "$out/lib/agent-device/bin/agent-device.mjs" \
        --set AGENT_DEVICE_NO_UPDATE_NOTIFIER 1 \
        --prefix PATH : "${sdk}/bin"
    '';
    meta = {
      description = "Pinned published agent-device CLI with bundled Android helpers";
      license = pkgs.lib.licenses.mit;
      platforms = [ "x86_64-linux" ];
    };
  };
  # A tiny static Linux helper also runs on the x86_64 Android kernel. It uses
  # pidfds to stop the exact guest process, never a check-then-kill bare PID.
  guestSignal =
    assert androidLab.abi == "x86_64";
    pkgs.runCommandCC "pi-re-guest-signal-x86_64"
      {
        buildInputs = [ pkgs.glibc.static ];
      }
      ''
        mkdir -p "$out/share/pi-re"
        $CC -O2 -Wall -Wextra -Werror -static \
          ${../home-manager/modules/ai/pi-re/guest-signal.c} \
          -o "$out/share/pi-re/guest-signal"
      '';
  python = pkgs.python3.withPackages (p: [
    p.frida-python
    p.mitmproxy
  ]);
  packages = [
    pkgs.jdk
    pkgs.nodejs
    pkgs.mitmproxy
    pkgs.openssl
    pkgs.cacert
    sdk
    pkgs.jadx
    pkgs.apktool
    pkgs.frida-tools
    python
    agentDevice
    fridaServer
    guestSignal
  ];
  environment = pkgs.symlinkJoin {
    name = "android-re-toolchain";
    paths = packages;
  };
in
{
  inherit
    sdk
    fridaVersion
    fridaServer
    guestSignal
    agentDevice
    python
    packages
    environment
    ;
  sdkRoot = "${sdk}/libexec/android-sdk";
}
