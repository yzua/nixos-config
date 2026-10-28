# Run a pinned, loopback-only Our Free Model proxy for Pi without importing accounts.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  dataDir = "${config.xdg.stateHome}/our-free-model";
  source = pkgs.fetchzip {
    url = "https://github.com/Ebony-Vinyl/dsh-our-free-model/archive/e27b0e8d75abaf71ecc53c6c6fef176c78570790.tar.gz";
    hash = "sha256-5YLotVVJ2DTpi+AoUZnb6kNLeAuodVWtt4G8dd9MJNI=";
  };
  proxy = pkgs.stdenvNoCC.mkDerivation {
    pname = "our-free-model";
    version = "2.7.2-e27b0e8";
    src = source;
    dontBuild = true;
    installPhase = ''
      runHook preInstall
      mkdir -p "$out/lib/our-free-model" "$out/bin"
      cp -r src packages vendor adapter package.json LICENSE "$out/lib/our-free-model/"
      cat > "$out/bin/our-free-model" <<EOF
      #!${pkgs.runtimeShell}
      exec ${lib.getExe pkgs.nodejs_24} "$out/lib/our-free-model/packages/standalone/cli.mjs" "\$@"
      EOF
      chmod +x "$out/bin/our-free-model"
      runHook postInstall
    '';
    meta = {
      description = "Local API proxy for upstream free model pools";
      homepage = "https://github.com/Ebony-Vinyl/dsh-our-free-model";
      license = lib.licenses.mit;
      mainProgram = "our-free-model";
    };
  };
  key = pkgs.writeShellScriptBin "our-free-model-key" ''
    exec ${lib.getExe pkgs.python3} -c 'import json,sys; print(json.load(open(sys.argv[1]))["forwardKey"])' \
      ${lib.escapeShellArg "${dataDir}/settings.json"}
  '';
  initialize = pkgs.writeText "our-free-model-initialize.py" ''
    import json
    import os
    from pathlib import Path

    directory = Path(${builtins.toJSON dataDir})
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    settings = directory / "settings.json"
    if not settings.exists():
        with open(settings, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            json.dump({
                "distribution": "managed",
                "updateCheckHours": 0,
                "tokenSaver": {"enabled": False},
                "localOptimize": {"enabled": False},
                "combos": [],
                "standaloneLanEnabled": False,
            }, stream)
  '';
in
{
  home.packages = [
    proxy
    key
  ];

  systemd.user.services.our-free-model = {
    Unit = {
      Description = "Our Free Model local API proxy";
      After = [ "network-online.target" ];
    };
    Service = {
      Type = "exec";
      ExecStartPre = "${lib.getExe pkgs.python3} ${initialize}";
      ExecStart = "${lib.getExe proxy} --data-dir ${lib.escapeShellArg dataDir} --port 18900 --no-lan";
      Restart = "on-failure";
      RestartSec = 5;
      UMask = "0077";
      Environment = [
        "HOME=${dataDir}"
        "XDG_CONFIG_HOME=${dataDir}/config"
        "XDG_DATA_HOME=${dataDir}/share"
        "XDG_STATE_HOME=${dataDir}/state"
        "DSH_HOME=${dataDir}/dsh"
      ];
      StateDirectory = "our-free-model";
      StateDirectoryMode = "0700";
      ProtectHome = "tmpfs";
      BindPaths = [ dataDir ];
      ProtectSystem = "strict";
      ReadWritePaths = [ dataDir ];
      NoNewPrivileges = true;
      PrivateTmp = true;
    };
    Install.WantedBy = [ "default.target" ];
  };
}
