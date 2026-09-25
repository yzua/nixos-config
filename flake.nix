{
  description = "NixOS configuration for nixos";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      nixosConfigurations.nixos = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [ ./configuration.nix ];
      };

      # Provides the command menu and Git before the first system switch.
      devShells.${system}.default = pkgs.mkShell {
        packages = [ pkgs.git pkgs.just ];
      };
    };
}
