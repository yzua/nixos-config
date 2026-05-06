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
      };

      constants = import ./shared/constants.nix;

      pkgs = import nixpkgs {
        inherit system;
        config = pkgConfig;
      };

      pkgsStable = import nixpkgs-stable {
        inherit system;
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
