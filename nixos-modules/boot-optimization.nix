# Defer non-critical services from blocking boot (reduces I/O contention by ~10-15s).
# Modules register their services via mySystem.boot.deferServices.

{
  config,
  lib,
  ...
}:

let
  deferredServices = config.mySystem.boot.deferServices;

  # Generate wantedBy overrides: remove each service from multi-user.target
  serviceOverrides = builtins.listToAttrs (
    map (name: {
      inherit name;
      value.wantedBy = lib.mkForce [ ];
    }) deferredServices
  );

  # Generate timers: start each deferred service 90s after boot
  timerEntries = builtins.listToAttrs (
    map (name: {
      name = "${name}-deferred";
      value = {
        description = "Deferred start for ${name}";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "90s";
          Unit = "${name}.service";
        };
      };
    }) deferredServices
  );
in
{
  options.mySystem.boot.deferServices = lib.mkOption {
    type = lib.types.listOf lib.types.str;
    default = [ ];
    description = "Services to defer from multi-user.target to a post-boot timer.";
  };

  config = {
    systemd.services = serviceOverrides;
    systemd.timers = timerEntries;
  };
}
