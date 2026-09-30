# Configure Voxtype transcription, dictation, and Pi voice actions.

{
  aiPackages,
  config,
  pkgs,
  ...
}:

let
  # Use Voxtype's recommended multilingual model for Arabic on a GPU.
  voxtypeModel = pkgs.fetchurl {
    url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin";
    hash = "sha256-H8cPd0046xaZk6w5Huo1fvR8iHV+9y7llDh5t+jivGk=";
  };
  # Silero detects silent recordings before they reach Whisper.
  voxtypeVadModel = pkgs.fetchurl {
    url = "https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin";
    hash = "sha256-KqJpt4XutTqCmDogUB3ffB2cSOM6tjpBORrGyff7aYc=";
  };
  # Numtide's Voxtype package is CPU-only; its CLI backend can use this
  # cached Vulkan build for fast transcription on the configured GPU.
  voxtypeWhisper = pkgs.whisper-cpp-vulkan;
  # Voxtype's CLI backend does not apply its language allowlist. Use the same
  # GPU Whisper model to select Arabic or English before decoding the clip.
  voxtypeWhisperLanguage = pkgs.stdenv.mkDerivation {
    pname = "voxtype-whisper-language";
    version = "1";
    src = ./whisper-language.cpp;
    dontUnpack = true;
    buildInputs = [ voxtypeWhisper ];
    buildPhase = ''
      runHook preBuild
      "$CXX" -std=c++17 -O2 "$src" \
        -I${voxtypeWhisper}/include \
        -L${voxtypeWhisper}/lib \
        -Wl,-rpath,${voxtypeWhisper}/lib \
        -lwhisper -lggml -lggml-base \
        -o voxtype-whisper-language
      runHook postBuild
    '';
    installPhase = ''
      runHook preInstall
      mkdir -p "$out/bin"
      install -m 755 voxtype-whisper-language "$out/bin/voxtype-whisper-language"
      runHook postInstall
    '';
  };
  voxtypeWhisperBilingual = pkgs.writeShellScript "voxtype-whisper-ar-en" ''
    model=""
    audio=""
    previous=""
    explicit_language=false
    for argument in "$@"; do
      case "$previous" in
        --model) model="$argument" ;;
        --file) audio="$argument" ;;
      esac
      if [ "$argument" = "--language" ]; then
        explicit_language=true
      fi
      previous="$argument"
    done

    if "$explicit_language"; then
      exec ${voxtypeWhisper}/bin/whisper-cli "$@"
    fi
    if [ -n "$model" ] && [ -n "$audio" ]; then
      if language="$(${voxtypeWhisperLanguage}/bin/voxtype-whisper-language "$model" "$audio")"; then
        exec ${voxtypeWhisper}/bin/whisper-cli --language "$language" "$@"
      fi
    fi
    exec ${voxtypeWhisper}/bin/whisper-cli --language auto "$@"
  '';
  voxtypeConfig = pkgs.formats.toml { };
  # Whisper sometimes emits these captions instead of recognized speech.
  voxtypeFilter = pkgs.writeShellScript "voxtype-filter-placeholders" ''
    transcription="$(${pkgs.coreutils}/bin/cat)"
    case "$transcription" in
      "[BLANK_AUDIO]" | "(speaking in foreign language)") ;;
      *) printf '%s' "$transcription" ;;
    esac
  '';
  # Keep the recording label opaque when the mic is quiet; upstream dims the
  # whole card, making application text show through the status message.
  voxtypeQml = pkgs.runCommand "voxtype-quickshell" { } ''
    cp -r ${aiPackages.voxtype.src}/quickshell "$out"
    chmod u+w "$out/OsdSurface.qml"
    substituteInPlace "$out/OsdSurface.qml" \
      --replace-fail '? 0.78 : 1.0' '? 1.0 : 1.0'
  '';
  voxtypeDaemon = pkgs.writeShellScript "voxtype-daemon" ''
    export PATH=${pkgs.quickshell}/bin:"$PATH"
    export VOXTYPE_OSD_QML_PATH=${voxtypeQml}
    exec ${aiPackages.voxtype}/bin/voxtype daemon
  '';
  voiceAction = import ./action.nix { inherit aiPackages pkgs; };
in
{
  home.packages = [
    aiPackages.voxtype
    voxtypeWhisper
    voiceAction
  ];

  xdg.configFile."voxtype/config.toml".source = voxtypeConfig.generate "voxtype-config.toml" {
    engine = "whisper";
    hotkey.enabled = false;
    audio.max_duration_secs = 30;
    audio.feedback = {
      enabled = true;
      theme = "subtle";
      volume = 0.5;
    };
    vad = {
      enabled = true;
      backend = "whisper";
      model = toString voxtypeVadModel;
      threshold = 0.5;
      min_speech_duration_ms = 100;
    };
    osd = {
      enabled = true;
      frontend = "quickshell";
      layout = "minimal";
      frame = {
        background = config.lib.stylix.colors.withHashtag.base00;
        border = "state";
        glow = false;
        halo = false;
      };
      visual.layers = [
        {
          type = "label";
          source = "state";
          color = "foreground";
          order = 10;
        }
      ];
    };
    whisper = {
      mode = "cli";
      whisper_cli_path = toString voxtypeWhisperBilingual;
      model = toString voxtypeModel;
      language = "auto";
      translate = false;
    };
    # Pasting handles Arabic without depending on the active keyboard layout.
    output = {
      mode = "paste";
      # Ghostty uses Ctrl+Shift+V for clipboard text; Ctrl+V reaches Codex as image paste.
      paste_keys = "ctrl+shift+v";
      post_process = {
        command = toString voxtypeFilter;
        fallback_on_empty = false;
      };
    };
  };

  systemd.user.services.voxtype = {
    Unit = {
      Description = "Voxtype voice-to-text daemon";
      PartOf = [ "graphical-session.target" ];
      After = [
        "graphical-session.target"
        "pipewire.service"
      ];
    };
    Service = {
      ExecStart = toString voxtypeDaemon;
      Restart = "on-failure";
      RestartSec = 5;
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };

  # GNOME has no key-release shortcut, so use the same toggle as Niri.
  dconf.settings."org/gnome/settings-daemon/plugins/media-keys".custom-keybindings = [
    "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voxtype/"
    "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voxtype-cancel/"
  ];
  dconf.settings."org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voxtype" = {
    name = "Toggle Voxtype dictation";
    command = "${voiceAction}/bin/voxtype-pi-action dictation-toggle";
    binding = "<Super>d";
  };
  dconf.settings."org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voxtype-cancel" = {
    name = "Cancel Voxtype dictation";
    command = "${voiceAction}/bin/voxtype-pi-action cancel";
    binding = "<Super><Shift>d";
  };
}
