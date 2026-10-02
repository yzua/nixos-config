# Provide a separate host-mode RE profile and rooted Android lab, leaving coding Pi unchanged.
{
  aiPackages,
  androidTools,
  config,
  lib,
  pkgs,
  setup,
  ...
}:
let
  resources = pkgs.runCommand "pi-re-resources" { } ''
    mkdir -p "$out/lib/pi-re"
    cp -r ${./.}/. "$out/lib/pi-re/"
    cp -r ${../../../../tests/fixtures/pi-re-android} "$out/lib/pi-re/fixture"
  '';
  python = "${androidTools.python}/bin/python3";
  runtime = pkgs.writeText "pi-re-runtime.json" (
    builtins.toJSON {
      inherit python;
      jdk = "${pkgs.jdk}";
      pi = lib.getExe aiPackages.pi;
      resources = "${resources}/lib/pi-re";
      # Explicit, immutable root integrations; never load the coding profile's directory.
      herdrIntegration = "${aiPackages.herdr}/share/herdr/integrations/pi/herdr-agent-state.ts";
      questionExtension = "${../pi/extensions/ask-user-question.ts}";
      sourceAgentDir = "${config.home.homeDirectory}/.pi/agent";
      android = setup.androidLab // {
        inherit (androidTools) sdkRoot;
        adb = "${androidTools.sdk}/bin/adb";
        emulator = "${androidTools.sdk}/bin/emulator";
        avdmanager = "${androidTools.sdk}/bin/avdmanager";
      };
      agentDevice = "${androidTools.agentDevice}/bin/agent-device";
      traffic = {
        mitmdump = "${pkgs.mitmproxy}/bin/mitmdump";
        openssl = "${pkgs.openssl}/bin/openssl";
        cacert = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
        port = setup.androidLab.proxyPort;
      };
      frida = {
        version = androidTools.fridaVersion;
        cli = "${pkgs.frida-tools}/bin/frida";
        javaBridge = "${pkgs.frida-tools}/${pkgs.python3.sitePackages}/frida_tools/bridges/java.js";
        inherit (androidTools) abi;
        server = "${androidTools.fridaServer}/share/pi-re/frida-server";
        signalHelper = "${androidTools.guestSignal}/share/pi-re/guest-signal";
      };
      capabilities = [
        {
          id = "android-static";
          skill = "android-static";
          tools = {
            jadx = "${pkgs.jadx}/bin/jadx";
            apktool = "${pkgs.apktool}/bin/apktool";
          };
          versions = {
            jadx = pkgs.jadx.version;
            apktool = pkgs.apktool.version;
          };
        }
        {
          id = "android-lab";
          skill = "android-runtime";
          tools = {
            adb = "${androidTools.sdk}/bin/adb";
            emulator = "${androidTools.sdk}/bin/emulator";
          };
          versions = {
            api = setup.androidLab.apiLevel;
            emulator = androidTools.emulatorVersion;
          };
        }
        {
          id = "agent-device";
          skill = "re-device";
          tools = {
            agent-device = "${androidTools.agentDevice}/bin/agent-device";
          };
          versions = {
            cli = androidTools.agentDevice.version;
          };
        }
        {
          id = "traffic";
          skill = "web-protocol";
          tools = {
            mitmdump = "${pkgs.mitmproxy}/bin/mitmdump";
          };
          versions = {
            mitmproxy = pkgs.mitmproxy.version;
          };
        }
        {
          id = "frida";
          skill = "android-runtime";
          tools = {
            server = "${androidTools.fridaServer}/share/pi-re/frida-server";
          };
          versions = {
            core = androidTools.fridaVersion;
            tools = pkgs.frida-tools.version;
          };
        }
      ]
      ++
        map
          (item: {
            inherit (item) id skill;
            tools = { };
          })
          [
            {
              id = "native";
              skill = "native-analysis";
            }
            {
              id = "browser";
              skill = "re-browser";
            }
            {
              id = "validation";
              skill = "finding-validation";
            }
            {
              id = "gateway";
              skill = "adapter-build";
            }
          ];
    }
  );
  launcher = pkgs.writeShellScriptBin "pi-re" ''
    export PI_RE_CONFIG=${runtime}
    export PATH=${lib.makeBinPath androidTools.packages}:"$PATH"
    exec ${python} ${resources}/lib/pi-re/launcher.py "$@"
  '';
in
{
  home.packages = [ launcher ];
  # Auth is copied only at runtime into private writable files, never into the store.
  home.activation.initializePiRe = lib.hm.dag.entryAfter [ "initializePi" ] ''
    if [ -v DRY_RUN ]; then
      echo "Would initialize independent writable RE profile from the coding login"
    else
      ${python} ${resources}/lib/pi-re/initialize.py \
        --agent-dir ${lib.escapeShellArg "${config.xdg.dataHome}/pi-re/agent"} \
        --state-dir ${lib.escapeShellArg "${config.xdg.stateHome}/pi-re"} \
        --source-agent-dir ${lib.escapeShellArg "${config.home.homeDirectory}/.pi/agent"}
    fi
  '';
}
