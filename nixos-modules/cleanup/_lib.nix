# Helper library for creating cleanup timers.

{
  pkgs,
  lib,
  systemdHelpers,
  user,
}:
let
  inherit (systemdHelpers)
    mkOneshotService
    mkNixosTimer
    ;

  bash = "${pkgs.bash}/bin/bash";
  find = "${pkgs.findutils}/bin/find";
  home = "/home/${user}";

  mkCleanupService =
    {
      name,
      description,
      execStart,
      postCommand ? null,
      serviceUser ? user,
    }:
    {
      systemd.services."cleanup-${name}" =
        (mkOneshotService {
          inherit description execStart;
          extraServiceConfig = {
            User = serviceUser;
          }
          // lib.optionalAttrs (postCommand != null) { ExecStartPost = postCommand; };
        })
        // {
          wantedBy = [ ];
        };
    };

  mkCleanupTimerUnit =
    {
      name,
      description,
      calendar,
      delay,
    }:
    {
      systemd.timers."cleanup-${name}" = mkNixosTimer {
        inherit description;
        onCalendar = calendar;
        unit = "cleanup-${name}.service";
        randomizedDelaySec = delay;
      };
    };
in
{
  inherit bash find home;

  mkFindCleanupTimer =
    {
      name,
      description,
      path,
      mtimeDays,
      calendar,
      delay,
      serviceUser ? user,
      removeEmptyDirs ? true,
    }:
    lib.recursiveUpdate
      (mkCleanupService {
        inherit name description serviceUser;
        execStart = "${bash} -c \"${find} '${path}' -type f -mtime +${toString mtimeDays} -delete 2>/dev/null || true\"";
        postCommand =
          if removeEmptyDirs then
            "${bash} -c \"${find} '${path}' -type d -empty -delete 2>/dev/null || true\""
          else
            null;
      })
      (mkCleanupTimerUnit {
        inherit
          name
          description
          calendar
          delay
          ;
      });

  mkCleanupTimer =
    {
      name,
      description,
      command,
      postCommand ? null,
      calendar,
      delay,
      serviceUser ? user,
    }:
    lib.recursiveUpdate
      (mkCleanupService {
        inherit
          name
          description
          postCommand
          serviceUser
          ;
        execStart = command;
      })
      (mkCleanupTimerUnit {
        inherit
          name
          description
          calendar
          delay
          ;
      });

  mkCachePurgeTimer =
    {
      name,
      description,
      binary,
      cacheCommand,
      calendar ? "monthly",
      delay ? "1h",
    }:
    lib.recursiveUpdate
      (mkCleanupService {
        inherit name description;
        execStart = "${bash} -c 'if command -v ${binary} >/dev/null 2>&1; then ${binary} ${cacheCommand} 2>/dev/null || true; fi'";
      })
      (mkCleanupTimerUnit {
        inherit
          name
          description
          calendar
          delay
          ;
      });
}
