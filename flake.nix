# Flake entry point: pin inputs and expose the system, home, and dev tools.

{
  description = "NixOS and Home Manager workstation configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    # Steam popup menus need the xwayland-satellite 0.8.3 fix.
    nixpkgs-xwayland-satellite.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    stylix = {
      url = "github:nix-community/stylix/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    sops-nix = {
      url = "github:Mic92/sops-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixcord = {
      url = "github:4evy/nixcord";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.home-manager.follows = "home-manager";
    };
    # Agent CLIs and desktop apps update faster than the stable Nixpkgs branch.
    # Keep this input's tested unstable Nixpkgs pin instead of using `follows`.
    llm-agents.url = "github:numtide/llm-agents.nix";
  };

  outputs =
    {
      nixpkgs,
      nixpkgs-xwayland-satellite,
      home-manager,
      stylix,
      sops-nix,
      nixcord,
      llm-agents,
      ...
    }:
    let
      # Change these values when adapting the flake to another workstation.
      setup = rec {
        system = "x86_64-linux";
        hostName = "PC";
        username = "yz";
        homeDirectory = "/home/${username}";
        # Preserve these values for an existing installation.
        stateVersion = {
          system = "26.05";
          home = "26.05";
        };
        # Etc/GMT signs are reversed: GMT-3 is a fixed UTC+03:00.
        timeZone = "Etc/GMT-3";
        locale = "en_US.UTF-8";
        keyboard = {
          layouts = [
            "us"
            "ara"
          ];
          toggle = "grp:caps_toggle";
        };
        monitors = [
          {
            match = "LG Electronics LG ULTRAWIDE 0x00021DA6";
            mode = "2560x1080@74.991";
            scale = 1;
            transform = "normal";
            position = {
              x = 0;
              y = 0;
            };
            primary = true;
          }
          {
            match = "Samsung Electric Company C24FG70 HTHJ200179";
            mode = "1920x1080@120.000";
            scale = 1;
            transform = "90";
            # Portrait screen on the right, with both screen centers aligned.
            position = {
              x = 2560;
              y = -420;
            };
            primary = false;
          }
        ];
        desktop = {
          voice = true;
          fullAutostart = true;
          vpnAutostart = true;
          touchpad = false;
          fontSizes = {
            desktop = 13;
            applications = 14;
            terminal = 16;
            popups = 13;
          };
          editorSettings = { };
        };
        peripherals = {
          keyboard = {
            vendorId = "359b";
            productId = "0004";
            # Confirmed VIA raw HID collection after the approved application flash.
            viaInterfaceNumber = "01";
          };
          lighting = {
            vendorId = "048d";
            productId = "8297";
          };
          cooler = {
            vendorId = "1b1c";
            productId = "0c18";
            openrgbName = "Corsair Hydro H100i Platinum";
            # Two stock RGB fans, four LEDs each; excludes the 16 pump LEDs.
            fanLedCount = 8;
            pumpLedCount = 16;
            # User-confirmed white balance; higher red/green restores yellow tint.
            pumpColor = [
              8
              8
              255
            ];
          };
          gpu = {
            pciVendor = "0x10de";
            pciDevice = "0x1f07";
            pciSubsystemVendor = "0x1462";
            pciSubsystemDevice = "0x3733";
            driver = "nvidia";
            adapterNamePrefix = "NVIDIA i2c adapter 1 at ";
            detectorName = "MSI RTX 2070 Gaming exact-ID validation";
            brightness = 80;
          };
          ram = {
            pciVendor = "0x8086";
            pciDevice = "0xa323";
            driver = "i801_smbus";
            adapterNamePrefix = "SMBus I801 adapter at ";
            moduleCount = 4;
          };
        };
        audio = {
          playbackDevice = "alsa_output.usb-HP__Inc_HyperX_Virtual_Surround_Sound_00000000-00.analog-stereo";
          playbackRoute = "Analog Output";
        };
        graphics = {
          videoDrivers = [ "nvidia" ];
          # Test the proprietary kernel module without GSP after GPU hangs.
          nvidiaOpen = false;
          nvidiaGsp = false;
        };
        # LAN streaming endpoints; reserve these leases in the router if possible.
        remoteDesktop = {
          hostAddress = "192.168.0.173";
          clientAddress = "192.168.0.230";
          hostInterface = "eno1";
          appName = "Desktop";
          resolution = "2560x1080";
          fps = 60;
          bitrateKbps = 20000;
          tv = {
            clientAddress = pi.home.samsung.host;
            appName = "TV Gaming (1440p)";
            # This 16:9 mode is advertised by the primary monitor; restore its
            # usual ultrawide mode when the TV application is quit in Moonlight.
            mode = "2560x1440@59.951";
          };
        };
        # Search backend is independent of Pi's selected chat model/provider.
        pi.webSearch = {
          provider = "codex-lb";
          model = "gpt-6.1-sol";
        };
        # Personal profile device facts; pairing credentials stay in private runtime state.
        pi.home.samsung = {
          host = "192.168.0.192";
          apps.nuvio = "NuvioTV001.NuvioTV";
        };
        # Read-only research workers; runtime RE jobs retain their separate limits.
        pi.research = {
          maxConcurrent = 4;
          defaultTimeoutSeconds = 600;
          maxTimeoutSeconds = 1800;
        };
        androidLab = {
          acceptLicense = true;
          apiLevel = "35";
          imageType = "google_apis";
          abi = "x86_64";
          avdName = "pi-re-api35";
          port = 5580;
          cores = 4;
          memoryMiB = 4096;
          bootTimeoutSeconds = 180;
          gpuMode = "swangle";
          hardwareVideoDecoder = false;
          display = {
            width = 720;
            height = 1600;
            density = 320;
          };
          proxyPort = 8089;
        };
        gitIdentity = {
          name = username;
          email = "git.remarry972@simplelogin.com";
          githubEmail = "260740417+yzua@users.noreply.github.com";
          signingKey = "${homeDirectory}/.ssh/id_ed25519.pub";
        };
      };
      # Keep host-specific facts here; the desktop remains the tooling default.
      laptopSetup = setup // {
        hostName = "laptop";
        # Preserve the laptop's installed baseline independently of the desktop.
        stateVersion = {
          system = "26.05";
          home = "26.05";
        };
        monitors = [
          {
            match = "eDP-1";
            mode = "2560x1600@60.000";
            scale = 2;
            transform = "normal";
            position = {
              x = 0;
              y = 0;
            };
            primary = true;
          }
        ];
        graphics.videoDrivers = [ "modesetting" ];
        # Leave room for the desktop and large multilingual speech model.
        androidLab = setup.androidLab // {
          cores = 2;
          memoryMiB = 2048;
          bootTimeoutSeconds = 300;
        };
        desktop = {
          voice = true;
          fullAutostart = true;
          vpnAutostart = true;
          touchpad = true;
          fontSizes = {
            desktop = 11;
            applications = 12;
            terminal = 13;
            popups = 11;
          };
          editorSettings = {
            "window.zoomLevel" = 0;
            "editor.fontSize" = 13;
            "terminal.integrated.fontSize" = 13;
          };
        };
        pi = setup.pi // {
          research = setup.pi.research // {
            maxConcurrent = 2;
          };
        };
      };
      inherit (setup) system;
      pkgs = import nixpkgs {
        inherit system;
        # Home Manager uses this package set; approve only the requested apps.
        config = {
          android_sdk.accept_license = setup.androidLab.acceptLicense;
          allowUnfreePredicate =
            pkg:
            let
              name = nixpkgs.lib.getName pkg;
            in
            builtins.elem name [
              "google-chrome"
              "vscode"
              "accela"
              "androidsdk"
              "platform-tools"
              "build-tools"
              "emulator"
              "platforms"
              "cmdline-tools"
              "system-image-${setup.androidLab.apiLevel}-${setup.androidLab.imageType}-${setup.androidLab.abi}"
            ]
            || nixpkgs.lib.hasPrefix "android-sdk-" name;
        };
      };
      androidTools = import ./packages/android-re-toolchain {
        inherit pkgs;
        inherit (setup) androidLab;
      };
      reaTools = import ./packages/rea { inherit pkgs; };
      openDesignPackage = pkgs.callPackage ./packages/open-design {
        # Reuse the configured browser instead of downloading a render binary.
        browser = pkgs.google-chrome;
      };
      # Reuse one formatter for `nix fmt` and the development shell.
      formatter = pkgs.nixfmt-tree.override {
        runtimeInputs = [ pkgs.shfmt ];
        settings.formatter.shfmt = {
          command = "shfmt";
          options = [
            "-i"
            "2"
            "-w"
          ];
          includes = [ "*.sh" ];
        };
        # This file is generated by nixos-generate-config; leave it unchanged.
        settings.formatter.nixfmt.excludes = [
          "hardware-configuration.nix"
          "**/hardware-configuration.nix"
        ];
      };
      mkHome =
        hostSetup: module:
        home-manager.lib.homeManagerConfiguration {
          inherit pkgs;
          extraSpecialArgs = {
            setup = hostSetup;
            androidTools = import ./packages/android-re-toolchain {
              inherit pkgs;
              inherit (hostSetup) androidLab;
            };
            inherit reaTools openDesignPackage;
            aiPackages = llm-agents.packages.${system};
            inherit nixcord;
          };
          modules = [
            module
            stylix.homeModules.stylix
            sops-nix.homeManagerModules.sops
          ];
        };
      home = mkHome setup ./home-manager/home.nix;
      laptopHome = mkHome laptopSetup ./home-manager/laptop.nix;
      piProfile =
        name:
        nixpkgs.lib.findFirst (
          package: nixpkgs.lib.getName package == name
        ) (throw "The selected Home Manager profile does not provide ${name}") home.config.home.packages;
    in
    {
      nixosConfigurations.${setup.hostName} = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = {
          inherit setup;
          xwaylandSatellite = nixpkgs-xwayland-satellite.legacyPackages.${system}.xwayland-satellite;
        };
        modules = [
          ./hosts/PC/default.nix
          sops-nix.nixosModules.sops
        ];
      };

      nixosConfigurations.${laptopSetup.hostName} = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = {
          setup = laptopSetup;
          xwaylandSatellite = nixpkgs-xwayland-satellite.legacyPackages.${system}.xwayland-satellite;
        };
        modules = [
          ./hosts/macbook/default.nix
          sops-nix.nixosModules.sops
        ];
      };

      homeConfigurations = {
        "${setup.username}@${setup.hostName}" = home;
        "${laptopSetup.username}@${laptopSetup.hostName}" = laptopHome;
      };
      checks.${system} = {
        "home-${setup.username}-${setup.hostName}" = home.activationPackage;
        "home-${laptopSetup.username}-${laptopSetup.hostName}" = laptopHome.activationPackage;
      };

      formatter.${system} = formatter;

      packages.${system} = {
        agent-reach = pkgs.callPackage ./packages/agent-reach { };
        opencli = pkgs.callPackage ./packages/agent-reach/opencli.nix { };
        accela = pkgs.callPackage ./packages/accela { };
        slssteam = pkgs.callPackage ./packages/slssteam { };
        open-design = openDesignPackage;
        room-cam = import ./packages/room-camera { inherit pkgs; };
        pi-base = piProfile "pi-base";
        pi-coding = piProfile "pi-coding";
        pi-home = piProfile "pi-home";
        pi-re = piProfile "pi-re";
        rea = reaTools.cli;
        rea-ghidra = reaTools.ghidra;
        # Tiny auditable ELF used only for static backend/agent qualification.
        rea-fixture = pkgs.runCommandCC "pi-re-rea-fixture" { } ''
          mkdir -p "$out/bin"
          $CC -O0 -g -fno-inline -fno-pie -no-pie \
            ${./tests/fixtures/pi-re-rea/native.c} -o "$out/bin/rea-fixture"
        '';
        android-re-sdk = androidTools.sdk;
        android-re-agent-device = androidTools.agentDevice;
        android-re-guest-signal = androidTools.guestSignal;
        android-re-toolchain = androidTools.environment;
      };
      devShells.${system} = {
        android-re = pkgs.mkShell {
          inherit (androidTools) packages;
          ANDROID_HOME = androidTools.sdkRoot;
          ANDROID_SDK_ROOT = androidTools.sdkRoot;
          AGENT_DEVICE_NO_UPDATE_NOTIFIER = "1";
        };

        # Project-only tooling; no change to the system or home packages.
        default = pkgs.mkShell {
          packages = [
            pkgs.git
            pkgs.just
            pkgs.age
            pkgs.sops
            home-manager.packages.${system}.default
            formatter
            pkgs.nixfmt
            pkgs.shfmt
            pkgs.statix
            pkgs.deadnix
            pkgs.shellcheck
            pkgs.biome
            pkgs.ruff
            pkgs.rumdl
            pkgs.python3
          ];
        };
      };
    };
}
