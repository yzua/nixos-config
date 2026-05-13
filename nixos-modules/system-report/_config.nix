# System report configuration: script derivations, systemd services, and timers.

{
  config,
  constants,
  lib,
  pkgs,
  pkgsStable,
  systemdHelpers,
  user,
  ...
}:

let
  inherit (systemdHelpers)
    mkServiceHardening
    mkOneshotService
    mkPersistentTimer
    ;

  cfg = config.mySystem.systemReport;

  # Standard hardening for system-report services
  reportHardening = mkServiceHardening { readWritePaths = [ cfg.outputDir ]; };

  featureFlags = {
    HAS_PROMETHEUS = lib.boolToString config.mySystem.observability.enable;
    HAS_LOKI = lib.boolToString config.mySystem.loki.enable;
    HAS_NETDATA = lib.boolToString config.mySystem.netdata.enable;
    HAS_SCRUTINY = lib.boolToString config.mySystem.scrutiny.enable;
    HAS_OPENSNITCH = lib.boolToString config.mySystem.opensnitch.enable;
    HAS_FAIL2BAN = lib.boolToString config.mySystem.fail2ban.enable;
    HAS_SECURE_BOOT = lib.boolToString config.mySystem.secureBoot.enable;
    SYSTEM_REPORT_DIR = cfg.outputDir;
    REPORT_USER = user;
    SYSTEM_REPORT_HELPERS = "${reportScriptsDir}/bin/report-helpers.sh";
    SYSTEM_REPORT_COLLECTORS = "${reportScriptsDir}/bin/report-collectors.sh";
    SYSTEM_REPORT_COLLECTORS_CORE = "${reportScriptsDir}/bin/report-collectors-core.sh";
    SYSTEM_REPORT_COLLECTORS_OBSERVABILITY = "${reportScriptsDir}/bin/report-collectors-observability.sh";
    SYSTEM_REPORT_COLLECTORS_SECURITY = "${reportScriptsDir}/bin/report-collectors-security.sh";
    AI_AGENT_LOG_DIR = "/home/${user}/.local/share/ai-agents/logs";
    NETDATA_URL = constants.urls.netdata;
    LOKI_URL = constants.urls.loki;
    SCRUTINY_URL = constants.urls.scrutiny;
  };

  mkReportService =
    description: execStart:
    mkOneshotService {
      inherit description execStart;
      extraServiceConfig = reportHardening;
    };

  # Build a directory with all report scripts included
  # Each script is wrapped as a derivation, then joined into a single directory
  reportScriptsDir =
    let
      mkScript = name: path: pkgs.writeScriptBin name (builtins.readFile path);
      reportLib = pkgs.runCommand "system-report-lib" { } ''
        mkdir -p $out/lib
        cp ${../../scripts/lib/error-patterns.sh} $out/lib/error-patterns.sh
        cp ${../../scripts/lib/log-dirs.sh} $out/lib/log-dirs.sh
      '';
    in
    pkgs.symlinkJoin {
      name = "system-report-scripts";
      paths = [
        reportLib
        (mkScript "report-helpers.sh" ../../scripts/system/report/report-helpers.sh)
        (mkScript "report-collectors.sh" ../../scripts/system/report/report-collectors.sh)
        (mkScript "report-collectors-core.sh" ../../scripts/system/report/report-collectors-core.sh)
        (mkScript "report-collectors-observability.sh" ../../scripts/system/report/report-collectors-observability.sh)
        (mkScript "report-collectors-security.sh" ../../scripts/system/report/report-collectors-security.sh)
      ];
    };

  featureFlagExports = lib.concatStringsSep "\n" (
    lib.mapAttrsToList (k: v: "export ${k}=\"\${${k}:-${v}}\"") featureFlags
  );

  reportScriptBase = pkgs.writeShellApplication {
    name = "system-report";
    runtimeInputs =
      with pkgs;
      [
        coreutils
        inetutils # hostname command
        jq
        curl
        systemd
        gawk
        gnused
        findutils
        bc
        gnugrep
      ]
      ++ lib.optionals config.services.vnstat.enable [ pkgs.vnstat ]
      ++ lib.optionals config.mySystem.fail2ban.enable [ pkgs.fail2ban ]
      ++ lib.optionals config.mySystem.secureBoot.enable [
        pkgsStable.mokutil
        pkgsStable.sbctl
      ];
    text = featureFlagExports + "\n" + builtins.readFile ../../scripts/system/report/system-report.sh;
  };

in
{
  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      reportScriptBase
      reportScriptsDir
    ];

    systemd = {
      services = {
        system-report-errors = mkReportService "Quick system error scan" "${reportScriptBase}/bin/system-report errors";

        system-report-full = mkReportService "Full system health report" "${reportScriptBase}/bin/system-report full";

        system-report-cleanup = mkReportService "Clean up old system reports" "${pkgs.findutils}/bin/find ${cfg.outputDir}/history -type f -mtime +${toString cfg.retentionDays} -delete";
      };

      timers = {
        system-report-errors = mkPersistentTimer {
          description = "Hourly system error scan";
          onCalendar = "hourly";
          randomizedDelaySec = "5m";
        };

        system-report-full = mkPersistentTimer {
          description = "Daily full system health report";
          onCalendar = "06:00";
          randomizedDelaySec = "15m";
        };

        system-report-cleanup = mkPersistentTimer {
          description = "Weekly cleanup of old system reports";
          onCalendar = "weekly";
          randomizedDelaySec = "1h";
        };
      };

      tmpfiles.rules = [
        "d ${cfg.outputDir} 0755 root root -"
        "d ${cfg.outputDir}/history 0755 root root -"
      ];
    };
  };
}
