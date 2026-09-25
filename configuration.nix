# Edit this configuration file to define what should be installed on
# your system. Help is available in the configuration.nix(5) man page, on
# https://search.nixos.org/options and in the NixOS manual (`nixos-help`).
#
# This file lives in ~/System and is imported by flake.nix.
# /etc/nixos is separate; use `just switch` to activate this flake explicitly.

{ config, pkgs, ... }:

{
  imports =
    [ # Include the results of the hardware scan.
      ./hardware-configuration.nix
    ];

  # Use the systemd-boot EFI boot loader.
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "nixos"; # Define your hostname.
  # networking.wireless.enable = true;  # Enables wireless support via wpa_supplicant.

  # Configure network proxy if necessary
  # networking.proxy.default = "http://user:password@proxy:port/";
  # networking.proxy.noProxy = "127.0.0.1,localhost,internal.domain";

  # Enable networking
  networking.networkmanager.enable = true;

  # Set your time zone.
  time.timeZone = "Asia/Amman";

  # Select internationalisation properties.
  #
  # English everywhere: menus, apps, dates and numbers stay English/Gregorian.
  #
  # This file used to force `ar_JO.UTF-8` into LC_TIME, LC_NUMERIC, LC_MONETARY
  # and friends via i18n.extraLocaleSettings. That block has been removed on
  # purpose -- it is what made `date` print "25 أيلول, 2026" instead of
  # "Sep 25 2026", and what put Arabic month names in every app and file
  # manager. Unset LC_* categories fall back to i18n.defaultLocale, which is
  # English, so deleting the block is all that is needed.
  i18n.defaultLocale = "en_US.UTF-8";

  # Arabic is available as a *keyboard layout* only (see
  # systemd.user.services.gnome-input-sources below). It is deliberately not a
  # system locale, so nothing in the UI switches to Arabic by itself.
  #
  # Note: there is no Arabic IBus engine in nixpkgs -- the engines offered by
  # i18n.inputMethod.ibus.engines are anthy, m17n, mozc, pinyin, rime, etc.
  # (all CJK/Thai/emoji). Arabic instead uses the xkb "ara" layout, which is
  # already present in xkeyboard-config and needs no extra package.
  i18n.inputMethod = {
    enable = true;
    type = "ibus";
  };

  # Enable the GNOME Desktop Environment.
  services.displayManager.gdm.enable = true;
  services.desktopManager.gnome.enable = true;

  programs.nix-ld.enable = true;

  # Configure keymap in X11. On GNOME/Wayland the active layouts come from
  # org.gnome.desktop.input-sources (set below); this is only the fallback for
  # plain X11 sessions.
  services.xserver.xkb = {
    layout = "us";
    variant = "";
  };

  # English (first entry = default) plus Arabic, switchable with Super+Space.
  #
  # This is applied as your user at session start so that it survives rebuilds.
  # It only sets the two layouts, so you can still add or reorder layouts in
  # Settings > Keyboard after logging in and nothing will fight you.
  #
  # The "ara" layout is a 4-level standard Arabic layout:
  #   level 1  Arabic letters   ض ص ث ق ف غ ع ه خ ح ج د ش س ي ب ل ا
  #   level 2  diacritics       fatha, damma, kasra, shadda...
  #   level 3  Arabic-Indic digits, on Shift+number
  systemd.user.services.gnome-input-sources = {
    description = "GNOME input sources: English (default) + Arabic";
    wantedBy = [ "graphical-session.target" ];
    after = [ "dconf.service" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = pkgs.lib.concatStringsSep " " [
        "${pkgs.glib}/bin/gsettings"
        "set"
        "org.gnome.desktop.input-sources"
        "sources"
        "\"[('xkb', 'us'), ('xkb', 'ara')]\""
      ];
    };
  };

  # Enable CUPS to print documents.
  services.printing.enable = true;

  # Enable sound with pipewire.
  services.pulseaudio.enable = false;
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
    # If you want to use JACK applications, uncomment this
    # jack.enable = true;
  };

  # Enable touchpad support (enabled default in most desktopManager).
  # services.libinput.enable = true;

  # Define a user account. Don't forget to set a password with ‘passwd’.
  users.users."yz" = {
    isNormalUser = true;
    description = "yz";
    extraGroups = [ "networkmanager" "wheel" ];
    packages = with pkgs; [
       wget
       nodejs          # Adds Node.js & npm
       telegram-desktop # Adds Telegram
    #  thunderbird
    ];
  };

  # Install firefox.
  programs.firefox.enable = true;

  # Allow unfree packages
  nixpkgs.config.allowUnfree = true;

  # Use the pinned flake and its small command menu for future rebuilds.
  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  environment.systemPackages = [ pkgs.git pkgs.just ];

  # List packages installed in system profile.
  # You can use https://search.nixos.org/ to find more packages (and options).
  # environment.systemPackages = with pkgs; [
  #   vim # Do not forget to add an editor to edit configuration.nix! The Nano editor is also installed by default.
  #   wget
  # ];

  # Some programs need SUID wrappers, can be configured further or are
  # started in user sessions.
  # programs.mtr.enable = true;
  # programs.gnupg.agent = {
  #   enable = true;
  #   enableSSHSupport = true;
  # };

  # List services that you want to enable:

  # Enable the OpenSSH daemon.
  # services.openssh.enable = true;

  # Open ports in the firewall.
  # networking.firewall.allowedTCPPorts = [ ... ];
  # networking.firewall.allowedUDPPorts = [ ... ];
  # Or disable the firewall altogether.
  # networking.firewall.enable = false;

  # Copy the NixOS configuration file and link it from the resulting system
  # (/run/current-system/configuration.nix). This is useful in case you
  # accidentally delete configuration.nix.
  # system.copySystemConfiguration = true;

  # This option defines the first version of NixOS you have installed on this particular machine,
  # and is used to maintain compatibility with application data (e.g., databases) created on older NixOS versions.
  #
  # Most users should NEVER change this value after the initial install, for any reason,
  # even if you have upgraded your system to a new NixOS release.
  #
  # This value does NOT affect the Nixpkgs version your packages and OS are pulled from,
  # so changing it will NOT upgrade your system - see https://nixos.org/manual/nixos/stable/#sec-upgrading for how to
  # actually do that.
  #
  # Do NOT change this value unless you have manually inspected all the changes it would make to your configuration,
  # and migrated your data accordingly.
  #
  # For more information, see `man configuration.nix` or https://nixos.org/manual/nixos/stable/options#opt-system.stateVersion .
  system.stateVersion = "26.05"; # Did you read the comment?

}
