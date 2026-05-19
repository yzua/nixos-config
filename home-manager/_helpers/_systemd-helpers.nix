# Home Manager systemd timer helpers.
#
# Timer functions are imported from shared/_systemd-timer-helpers.nix which
# contains both NixOS and HM variants side-by-side. Use mkHmTimer here;
# use mkNixosTimer in nixos-modules/helpers/_systemd-helpers.nix.

{ lib }:
let
  timerHelpers = import ../../shared/_systemd-timer-helpers.nix { inherit lib; };
in
{
  inherit (timerHelpers) mkHmTimer;
}
