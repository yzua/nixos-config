# Home Manager systemd unit helpers.
#
# NOTE: This is the Home Manager variant — it outputs HM systemd format
# ({ Unit.Description; Timer = { ... }; Install.WantedBy = ... }).
# The NixOS equivalent lives in nixos-modules/helpers/_systemd-helpers.nix
# and outputs NixOS systemd format ({ description; wantedBy; timerConfig = { ... } }).
# They share the name mkPersistentTimer but produce different schemas because
# HM and NixOS use different systemd option structures.
{ lib }:
rec {
  mkPersistentTimer =
    {
      description,
      onCalendar ? "weekly",
      randomizedDelaySec ? null,
      unit ? null,
    }:
    {
      Unit.Description = description;
      Timer = {
        OnCalendar = onCalendar;
        Persistent = true;
      }
      // lib.optionalAttrs (randomizedDelaySec != null) { RandomizedDelaySec = randomizedDelaySec; }
      // lib.optionalAttrs (unit != null) { Unit = unit; };
      Install.WantedBy = [ "timers.target" ];
    };
}
