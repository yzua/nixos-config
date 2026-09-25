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

      # Provides just before the first system switch installs it.
      devShells.${system}.default = pkgs.mkShell {
        packages = [ pkgs.just ];
      };
    };
}
