{
  description = "NixOS configuration for nixos";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    home-manager = {
      url = "github:nix-community/home-manager/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, home-manager, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      home = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        modules = [ ./home-manager/home.nix ];
      };
    in
    {
      nixosConfigurations.nixos = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [ ./configuration.nix ];
      };

      homeConfigurations."yz@nixos" = home;
      checks.${system}.home-yz-nixos = home.activationPackage;

      # Provides the command menu and Git before the first system switch.
      devShells.${system}.default = pkgs.mkShell {
        packages = [ pkgs.git pkgs.just home-manager.packages.${system}.default ];
      };
    };
}
