# Install pinned AI applications and import agent settings without managing mutable data.

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
  # Codex 0.157 enables daemon auto-start, but this source-built package lacks
  # the complete-package metadata needed to launch the daemon. Override only
  # this feature for the CLI until the upstream packaging is fixed; leave the
  # user's mutable Codex config and credentials outside Nix.
  codexCli = pkgs.symlinkJoin {
    name = "codex-no-auto-daemon";
    paths = [ aiPackages.codex ];
    nativeBuildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/codex" --add-flags "--disable daemon_auto_start"
    '';
  };
  # Numtide's V2 package exposes `opencode2`; provide the usual CLI name and
  # generate matching Zsh completion from that package.
  opencodeCli = pkgs.symlinkJoin {
    name = "opencode-cli";
    paths = [
      (pkgs.writeShellScriptBin "opencode" ''
        exec ${aiPackages.opencode2}/bin/opencode2 "$@"
      '')
    ];
    postBuild = ''
      mkdir -p "$out/share/zsh/site-functions"
      HOME="$TMPDIR" \
        XDG_CONFIG_HOME="$TMPDIR/config" \
        XDG_DATA_HOME="$TMPDIR/data" \
        XDG_CACHE_HOME="$TMPDIR/cache" \
        XDG_STATE_HOME="$TMPDIR/state" \
        ${aiPackages.opencode2}/bin/opencode2 --completions zsh > "$out/share/zsh/site-functions/_opencode"
    '';
  };
in
{
  imports = [
    ./herdr.nix
    ./pnpm-tools.nix
    ./skills.nix
  ];

  # Executables come from Numtide; settings, logins, and session data remain
  # in the user's home until deliberately migrated one app at a time.
  home.packages = with aiPackages; [
    antigravity-cli
    chatgpt
    codexCli
    ctx
    executor
    herdr
    officecli
    opencodeCli
    opencode2
    pi
    skills
    t3code-desktop
    voxtype
    voxtypeWhisper
    zcode
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
    command = "${aiPackages.voxtype}/bin/voxtype record toggle";
    binding = "<Super>d";
  };
  dconf.settings."org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voxtype-cancel" = {
    name = "Cancel Voxtype dictation";
    command = "${aiPackages.voxtype}/bin/voxtype record cancel";
    binding = "<Super><Shift>d";
  };
}
