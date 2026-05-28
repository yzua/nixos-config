# Entry point: flake-based NixOS + Home Manager configuration.

{
  description = "Personal NixOS configuration";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    nixpkgs-stable.url = "github:nixos/nixpkgs/nixos-25.11";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    stylix = {
      url = "github:danth/stylix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    sops-nix = {
      url = "github:Mic92/sops-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    niri.url = "github:sodiboo/niri-flake"; # Do NOT follow nixpkgs — mesa compatibility

    noctalia = {
      url = "github:noctalia-dev/noctalia-shell";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nixcord = {
      url = "github:KaylorBen/nixcord";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-index-database = {
      url = "github:nix-community/nix-index-database";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    gitanon = {
      url = "github:yzua/gitanon";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    herdr = {
      url = "github:ogulcancelik/herdr/v0.6.2";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      nixpkgs-stable,
      home-manager,
      ...
    }@inputs:
    let
      inherit (constants) system;
      homeStateVersion = "25.11";
      user = constants.user.handle;

      hosts = import ./hosts/_inventory.nix;

      activeHosts = builtins.filter (host: host.enabled) hosts;

      forEachHost =
        hostList: buildEntry: nixpkgs.lib.foldl' (configs: host: configs // buildEntry host) { } hostList;

      forEachActiveHost = forEachHost activeHosts;
      forEachInventoryHost = forEachHost hosts;

      # Single source of truth for all nixpkgs instances
      pkgConfig = {
        allowUnfree = true;
        allowBroken = false;
        allowInsecure = false;
        allowUnsupportedSystem = false;
        android_sdk.accept_license = true;
      };

      nixpkgsOverlays = [
        (_final: prev: {
          openldap =
            if (prev.openldap.version or "") == "2.6.13" then
              prev.openldap.overrideAttrs (_old: {
                # openldap 2.6.13's syncrepl test fails on this nixpkgs revision
                # and blocks FHS app closures such as Bottles/Lutris.
                doCheck = false;
              })
            else
              prev.openldap;

          aw-server-rust =
            if (prev.aw-server-rust.version or "") == "0.13.2" then
              let
                sources = prev.fetchFromGitHub {
                  owner = "ActivityWatch";
                  repo = "activitywatch";
                  rev = "v${prev.aw-server-rust.version}";
                  hash = "sha256-Z3WAg3b1zN0nS00u0zIose55JXRzQ7X7qy39XMY7Snk=";
                  fetchSubmodules = true;
                };

                aw-webui = prev.buildNpmPackage {
                  pname = "aw-webui";
                  inherit (prev.aw-server-rust) version;

                  src = "${sources}/aw-server-rust/aw-webui";
                  npmDepsHash = "sha256-fPk7UpKuO3nEN1w+cf9DIZIG1+XRUk6PJfVmtpC30XE=";

                  makeCacheWritable = true;
                  npmFlags = [ "--legacy-peer-deps" ];

                  patches = [
                    (prev.replaceVars "${nixpkgs}/pkgs/applications/office/activitywatch/commit-hash.patch" {
                      commit_hash = sources.rev;
                    })
                  ];

                  installPhase = ''
                    runHook preInstall
                    mv dist $out
                    mv media/logo/logo.{png,svg} $out
                    runHook postInstall
                  '';

                  # Upstream's npm test currently fails because @vue/vue2-jest
                  # requires vue-template-compiler but aw-webui does not vendor it.
                  doCheck = false;
                };
              in
              prev.aw-server-rust.overrideAttrs (old: {
                env = (old.env or { }) // {
                  AW_WEBUI_DIR = aw-webui;
                };
              })
            else
              prev.aw-server-rust;
        })
      ];

      constants = import ./shared/constants.nix;

      pkgs = import nixpkgs {
        inherit system;
        overlays = nixpkgsOverlays;
        config = pkgConfig;
      };

      pkgsStable = import nixpkgs-stable {
        inherit system;
        overlays = nixpkgsOverlays;
        config = pkgConfig;
      };

      optionHelpers = import ./shared/_option-helpers.nix { inherit (nixpkgs) lib; };
      secretLoader = import ./home-manager/_helpers/_secret-loader.nix;
      hmSystemdHelpers = import ./home-manager/_helpers/_systemd-helpers.nix { inherit (nixpkgs) lib; };

      # Args shared between NixOS and Home Manager specialArgs
      sharedArgs = {
        inherit
          inputs
          user
          pkgsStable
          nixpkgsOverlays
          constants
          optionHelpers
          ;
      };

      makeSystem =
        { hostname, stateVersion }:
        nixpkgs.lib.nixosSystem {
          inherit system;
          specialArgs = sharedArgs // {
            inherit stateVersion hostname pkgConfig;
            systemdHelpers = import ./nixos-modules/helpers/_systemd-helpers.nix { inherit (nixpkgs) lib; };
          };
          modules = [ ./hosts/${hostname}/configuration.nix ];
        };

      makeHome =
        host:
        home-manager.lib.homeManagerConfiguration {
          inherit pkgs;
          extraSpecialArgs = sharedArgs // {
            inherit homeStateVersion secretLoader hmSystemdHelpers;
            inherit (host) hostname;
          };
          modules = [
            ./home-manager/home.nix
            inputs.nix-index-database.homeModules.nix-index
          ];
        };
    in
    {
      nixosConfigurations = forEachActiveHost (host: {
        "${host.hostname}" = makeSystem { inherit (host) hostname stateVersion; };
      });

      homeConfigurations = forEachActiveHost (host: {
        "${user}@${host.hostname}" = makeHome host;
      });

      checks.${system} = forEachInventoryHost (host: {
        "nixos-${host.hostname}" =
          (makeSystem { inherit (host) hostname stateVersion; }).config.system.build.toplevel;
        "home-${user}-${host.hostname}" = (makeHome host).activationPackage;
      });

      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          statix
          deadnix
          shellcheck
          nixfmt-tree
        ];
      };

      formatter.${system} = pkgs.nixfmt-tree;
    };
}
