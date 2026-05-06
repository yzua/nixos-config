# Noctalia Shell settings (theme, dock, wallpaper, OSD, control center)

{
  constants,
  ...
}:

let
  mkControlCenterCard = id: enabled: {
    inherit id enabled;
  };
  mkSessionPowerOption = action: keybind: {
    inherit action keybind;
    command = "";
    countdownEnabled = true;
    enabled = true;
  };
in

{
  programs.noctalia-shell.settings = {
    colorSchemes = {
      predefinedScheme = "GruvboxAlt";
      darkMode = true;
    };

    location = {
      name = "";
      use12hourFormat = true;
      hideWeatherTimezone = true;
      hideWeatherCityName = true;
    };

    nightLight = {
      enabled = true;
      dayTemp = 6500;
      nightTemp = 3500;
    };

    notifications = {
      monitors = [ "HDMI-A-1" ];
      location = "top_right";
      backgroundOpacity = 0.96;
      respectExpireTimeout = true;
      lowUrgencyDuration = 3;
      normalUrgencyDuration = 6;
      criticalUrgencyDuration = 10;
    };

    general = {
      compactLockScreen = false;
      showChangelogOnStartup = false;
      dimmerOpacity = 0.72;
      scaleRatio = 0.95;
      animationDisabled = false;
      animationSpeed = 1.2;
      enableLockScreenMediaControls = false;
      enableShadows = false;
      enableBlurBehind = true;
      passwordChars = false;
      radiusRatio = 0;
      iRadiusRatio = 0;
      boxRadiusRatio = 0;
      screenRadiusRatio = 0;
      keybinds.keyEnter = [
        "Return"
        "Enter"
      ];
    };

    ui = {
      scrollbarAlwaysVisible = true;
      translucentWidgets = false;
      panelBackgroundOpacity = 1;
      boxBorderEnabled = true;
      settingsPanelSideBarCardStyle = false;
    };

    bar = {
      barType = "floating";
      density = "default";
      showOutline = false;
      showCapsule = false;
      widgetSpacing = 6;
      contentPadding = 2;
      fontScale = 1;
      enableExclusionZoneInset = true;
      backgroundOpacity = 1;
      floating = true;
      marginVertical = 0;
      marginHorizontal = 6;
      frameThickness = 0;
      frameRadius = 0;
      outerCorners = false;
      showOnWorkspaceSwitch = true;
      mouseWheelAction = "none";
      reverseScroll = false;
      mouseWheelWrap = true;
      middleClickAction = "none";
      middleClickFollowMouse = false;
      middleClickCommand = "";
      rightClickAction = "controlCenter";
      rightClickFollowMouse = true;
      rightClickCommand = "";
    };

    appLauncher = {
      overviewLayer = true;
      enableClipboardHistory = true;
      enableClipboardSmartIcons = true;
      enableClipboardChips = true;
      viewMode = "list";
      showCategories = true;
      showIconBackground = false;
      terminalCommand = "${constants.terminal} -e";
    };

    wallpaper = {
      enabled = false;
      fillMode = "crop";
      transitionDuration = 1500;
      transitionType = [ "fade" ];
      automationEnabled = true;
      wallpaperChangeMode = "random";
      randomIntervalSec = 600;
    };

    systemMonitor = {
      enableDgpuMonitoring = true;
      useCustomColors = false;
      warningColor = constants.color.blue; # #83a598
      criticalColor = constants.color.red; # #fb4934
    };

    audio = {
      spectrumFrameRate = 30;
      visualizerType = "mirrored";
      volumeFeedbackSoundFile = "";
    };

    dock = {
      enabled = false;
      displayMode = "auto_hide";
      position = "bottom";
      showLauncherIcon = false;
      launcherPosition = "end";
      launcherUseDistroLogo = false;
      launcherIcon = "";
      launcherIconColor = "none";
      groupApps = false;
      groupContextMenuMode = "extended";
      groupClickAction = "cycle";
      groupIndicatorStyle = "dots";
      showDockIndicator = false;
      indicatorThickness = 3;
      indicatorColor = "primary";
      indicatorOpacity = 0.6;
      pinnedApps = [
        "brave-browser"
        constants.terminalAppId
        constants.editor
        "vesktop"
        "org.telegram.desktop"
      ];
    };

    osd = {
      enabled = true;
      monitors = [ "HDMI-A-1" ];
      location = "top_right";
      autoHideMs = 2000;
    };

    network = {
      networkPanelView = "wifi";
      bluetoothAutoConnect = true;
    };

    brightness = {
      backlightDeviceMappings = [ ];
    };

    noctaliaPerformance = {
      disableWallpaper = true;
      disableDesktopWidgets = true;
    };

    sessionMenu.powerOptions = [
      (mkSessionPowerOption "lock" "1")
      (mkSessionPowerOption "suspend" "2")
      (mkSessionPowerOption "hibernate" "3")
      (mkSessionPowerOption "reboot" "4")
      (mkSessionPowerOption "logout" "5")
      (mkSessionPowerOption "shutdown" "6")
      (mkSessionPowerOption "rebootToUefi" "")
    ];

    hooks = {
      enabled = true;
      screenLock = "playerctl pause";
      screenUnlock = "playerctl play";
      colorGeneration = "";
    };

    plugins = {
      notifyUpdates = true;
    };

    idle = {
      enabled = false;
      screenOffTimeout = 600;
      lockTimeout = 660;
      suspendTimeout = 1800;
      fadeDuration = 5;
      screenOffCommand = "";
      lockCommand = "";
      suspendCommand = "";
      resumeScreenOffCommand = "";
      resumeLockCommand = "";
      resumeSuspendCommand = "";
      customCommands = "[]";
    };

    desktopWidgets = {
      enabled = true;
      overviewEnabled = true;
      gridSnap = true;
      gridSnapScale = false;
    };

    controlCenter = {
      cards = [
        (mkControlCenterCard "profile-card" true)
        (mkControlCenterCard "shortcuts-card" true)
        (mkControlCenterCard "audio-card" true)
        (mkControlCenterCard "brightness-card" true)
        (mkControlCenterCard "weather-card" true)
        (mkControlCenterCard "media-sysmon-card" true)
      ];
    };
  };
}
