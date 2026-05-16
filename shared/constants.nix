# Shared constants used across NixOS and Home Manager configurations.
# Single source of truth for terminal, editor, font, theme, and keyboard settings.
# Passed via flake specialArgs (NixOS) and extraSpecialArgs (Home Manager).

let
  localhost = "127.0.0.1";

  # Service ports — single source of truth for localhost services.
  # Referenced by NixOS modules and Glance dashboard health checks.
  ports = {
    glance = 8082;
    zellij-web = 8083;
    netdata = 19999;
    grafana = 3001;
    prometheus = 9090;
    alertmanager = 9093;
    scrutiny = 8080;
    influxdb = 8086;
    loki = 3100;
    loki-grpc = 9096;
    alloy = 12345;
    ntfy-bridge = 8090;
    i2pd-socks = 4447;
    i2pd-webconsole = 7070;
    activitywatch = 5600;
    otel = 4317;
    vnc = 5900;
    vnc-web = 6080;
    localsend = 53317;
    tor-socks = 9050;
    tor-dns = 9053;
    socks = 1080;
    dns = 53;
    cups = 631;
    devServer = 3000;
  };
in
{
  # User Identity (Git, GitHub, Contact)
  user = {
    handle = "yz";
    name = "yz";
    email = "git.remarry972@simplelogin.com";
    githubEmail = "260740417+yzua@users.noreply.github.com";
    signingKey = "0x9C3EC618CFE2EB3D";
  };

  # Terminal emulator
  terminal = "ghostty";
  terminalAppId = "com.mitchellh.ghostty"; # Wayland app-id — used in window rules and dock

  # Default text editor
  editor = "code";
  editorAppId = "code|Code"; # Wayland app-id — used in window rules (lowercase for vscode-fhs, Code for upstream, code-url-handler for URL opens)

  # Fonts
  font = {
    mono = "JetBrains Mono";
    monoNerd = "JetBrainsMono Nerd Font";
    size = 13;
    sizeApplications = 11;
  };

  # Theme (GruvboxAlt)
  theme = "gruvbox-dark-soft";

  # Locale
  locale = "en_US.UTF-8";

  # Application-level theme names (not all apps support base16/Stylix)
  themeNames = {
    bat = "gruvbox-dark";
    opencode = "gruvbox-dark";
  };

  # Gruvbox color palette (base16 colors)
  # Used by applications that don't support Stylix theming
  color = {
    # Hard/Background shades
    bg_hard = "#1d2021"; # base00
    bg = "#282828"; # base01
    bg_soft = "#32302f"; # bg0_hard
    bg0 = "#3c3836"; # bg0
    bg1 = "#504945"; # bg1
    outline = "#57514e"; # GruvboxAlt outline/border

    # Foreground shades
    fg0 = "#ebdbb2"; # base06 (primary light foreground)
    fg_light = "#fbf1c7"; # base05 (bright foreground / light-mode background)
    fg_dark = "#665c54"; # bg3

    # Accent colors
    red = "#fb4934"; # base08 (bright)
    red_dim = "#cc241d"; # base08 (dim)

    green = "#b8bb26"; # base0B (bright)
    green_dim = "#98971a"; # base0B (dim)

    yellow = "#fabd2f"; # base0A (bright)
    yellow_dim = "#d79921"; # base0A (dim)

    blue = "#83a598"; # base0D (bright)
    blue_dim = "#458588"; # base0D (dim)

    purple = "#d3869b"; # base0E (bright)
    purple_dim = "#b16286"; # base0E (dim)

    aqua = "#8ec07c"; # base0C (bright)
    aqua_dim = "#689d6a"; # base0C (dim)

    orange = "#fe8019"; # base09 (bright)
    orange_dim = "#d65d0e"; # base09 (dim)

    gray = "#928374"; # base04 (bright gray)
    gray_dim = "#a89984"; # base05 (dim gray)
  };

  # Keyboard layout (XKB)
  keyboard = {
    layout = "us,ara";
    variant = ",qwerty";
    options = "grp:caps_toggle,grp_led:caps";
  };

  # Mullvad SOCKS5 proxy endpoints for browser profiles.
  # Never mix proxies - each profile gets a dedicated exit.
  proxies = {
    # LibreWolf profiles
    librewolf = {
      personal = "se-sto-wg-socks5-002.relays.mullvad.net"; # Sweden
      work = "de-fra-wg-socks5-003.relays.mullvad.net"; # Germany
      banking = "nl-ams-wg-socks5-005.relays.mullvad.net"; # Netherlands
      shopping = "ro-buh-wg-socks5-001.relays.mullvad.net"; # Romania
      illegal = "ch-zrh-wg-socks5-002.relays.mullvad.net"; # Switzerland
    };
    brave = {
      personal = "fi-hel-wg-socks5-001.relays.mullvad.net"; # Finland
    };
    # I2P local daemon
    i2pd = "127.0.0.1"; # Local I2P daemon (port 4447)
  };

  # Loopback address — single source of truth for localhost-only service bindings.
  inherit localhost;

  # Service ports — single source of truth for localhost services.
  inherit ports;

  # Localhost service URLs — auto-derived from ports + localhost.
  # Used by monitoring modules (prometheus-grafana, glance, system-report).
  urls = builtins.mapAttrs (_name: port: "http://${localhost}:${toString port}") ports;

  # Docker default bridge gateway IP.
  # Used by dnscrypt-proxy (listen address) and Docker daemon (DNS).
  dockerBridge = "172.17.0.1";

  # Paths relative to HOME for repo-local resources.
  paths = {
    scripts = "System/scripts";
    screens = "Screens";
    opencodeLogDir = ".local/share/opencode/log";
    codexLogDir = ".codex/log";
    aiAgentsLogDir = ".local/share/ai-agents/logs";
    sopsKeyDir = ".config/sops/age/keys.txt";
    androidSdk = "Android/Sdk";
    systemRepo = "System";
    eglVendorFile = "/run/opengl-driver/share/glvnd/egl_vendor.d/50_mesa.json";
  };

  # System architecture — used by flake.nix and package meta.platforms.
  system = "x86_64-linux";
}
