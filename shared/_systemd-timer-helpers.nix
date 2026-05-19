# Shared systemd timer helpers for NixOS and Home Manager.
#
# NixOS and HM use different systemd option structures, so this file provides
# two explicitly-named functions to prevent accidental cross-world usage:
#
#   mkNixosTimer — { description; wantedBy; timerConfig = { ... } }
#   mkHmTimer    — { Unit.Description; Timer = { ... }; Install.WantedBy }
{ lib }:
{
  mkNixosTimer =
    {
      description,
      onCalendar,
      unit ? null,
      randomizedDelaySec ? null,
      wantedBy ? [ "timers.target" ],
    }:
    {
      inherit description wantedBy;
      timerConfig = {
        OnCalendar = onCalendar;
        Persistent = true;
      }
      // lib.optionalAttrs (unit != null) { Unit = unit; }
      // lib.optionalAttrs (randomizedDelaySec != null) { RandomizedDelaySec = randomizedDelaySec; };
    };

  mkHmTimer =
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
