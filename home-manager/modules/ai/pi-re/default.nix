# Add reviewed RE resources and a rooted Android lab to the shared Pi base.
{
  aiPackages,
  androidTools,
  config,
  lib,
  pkgs,
  reaTools,
  setup,
  ...
}:
let
  base = import ../pi-base/resources.nix { inherit aiPackages pkgs setup; };
  contract = pkgs.writeText "pi-re-contract.md" (
    builtins.readFile base.instructions + "\n" + builtins.readFile ./contract.md
  );
  resources = pkgs.runCommand "pi-re-resources" { } ''
    mkdir -p "$out/lib/pi-re"
    cp -r ${./.}/. "$out/lib/pi-re/"
    chmod u+w "$out/lib/pi-re/contract.md"
    cp ${contract} "$out/lib/pi-re/contract.md"
    cp -r ${../../../../tests/fixtures/pi-re-android} "$out/lib/pi-re/fixture"
    mkdir -p "$out/lib/pi-re/upstream"
    cp -r ${reaTools.cli}/lib/rea/skills/reverse-engineer-anything "$out/lib/pi-re/upstream/"
    cp ${reaTools.cli}/lib/rea/LICENSE "$out/lib/pi-re/upstream/LICENSE-REA"
  '';
  # Reuse the already managed pinned CLI, not an ambient PATH installation.
  chromeDevtools = builtins.head (import ../chrome-devtools { inherit pkgs; }).home.packages;
  python = "${androidTools.python}/bin/python3";
  reaAdb = pkgs.writeShellScript "pi-re-rea-adb" ''
    exec ${python} ${resources}/lib/pi-re/rea_adb.py "$@"
  '';
  runtime = pkgs.writeText "pi-re-runtime.json" (
    builtins.toJSON {
      inherit python;
      jdk = "${pkgs.jdk}";
      inherit (base) pi commonExtensions commonSkills;
      resources = "${resources}/lib/pi-re";
      reaSkill = "${resources}/lib/pi-re/upstream/reverse-engineer-anything";
      # Explicit, immutable root integrations; never load the coding profile's directory.
      webSearchExtension = "${base.directory}/web-search/index.ts";
      webFetchExtension = "${base.directory}/web-fetch/index.ts";
      research = setup.pi.research;
      browser = {
        cli = "${chromeDevtools}/bin/chrome-devtools";
        executable = "${pkgs.google-chrome}/bin/google-chrome-stable";
        daemonScript = "${chromeDevtools}/lib/chrome-devtools-mcp/node_modules/chrome-devtools-mcp/build/src/daemon/daemon.js";
      };
      agentDir = ".pi/agent";
      android = setup.androidLab // {
        inherit (androidTools) sdkRoot;
        adb = "${androidTools.sdk}/bin/adb";
        emulator = "${androidTools.sdk}/bin/emulator";
        avdmanager = "${androidTools.sdk}/bin/avdmanager";
      };
      rea = {
        cli = "${reaTools.cli}/bin/rea";
        ghidra = "${reaTools.ghidra}/lib/ghidra";
        jdk = "${reaTools.jdk}";
        jadxJar = "${reaTools.jadxEngine}";
        environment = {
          REA_ADB_PATH = "${reaAdb}";
          REA_APKTOOL_COMMAND = "${pkgs.apktool}/bin/apktool";
          REA_MITMDUMP_COMMAND = "${pkgs.mitmproxy}/bin/mitmdump";
          REA_TSHARK_COMMAND = "${pkgs.wireshark-cli}/bin/tshark";
          REA_CAPINFOS_COMMAND = "${pkgs.wireshark-cli}/bin/capinfos";
          REA_TSHARK_PRLIMIT_COMMAND = "${pkgs.util-linux}/bin/prlimit";
          REA_OBJDUMP_COMMAND = "${pkgs.binutils}/bin/objdump";
          REA_BROWSER_EXECUTABLE = "${pkgs.google-chrome}/bin/google-chrome-stable";
          REA_EVM_PRLIMIT_COMMAND = "${pkgs.util-linux}/bin/prlimit";
          REA_FIRMWARE_PRLIMIT_COMMAND = "${pkgs.util-linux}/bin/prlimit";
          REA_JAVASCRIPT_PRLIMIT_COMMAND = "${pkgs.util-linux}/bin/prlimit";
        };
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
          id = "rea";
          skill = "rea-analysis";
          tools = {
            rea = "${reaTools.cli}/bin/rea";
            ghidra = "${reaTools.ghidra}/lib/ghidra/support/analyzeHeadless";
            java = "${reaTools.jdk}/bin/java";
            javac = "${reaTools.jdk}/bin/javac";
          };
          artifacts = {
            jadxJar = "${reaTools.jadxEngine}";
          };
          versions = {
            rea = reaTools.cli.version;
            ghidra = reaTools.ghidra.version;
            jdk = reaTools.jdk.version;
            jadxEngine = "0.7.1";
          };
        }
        {
          id = "rea-network";
          skill = "rea-analysis";
          tools = {
            rea = "${reaTools.cli}/bin/rea";
            mitmdump = "${pkgs.mitmproxy}/bin/mitmdump";
            tshark = "${pkgs.wireshark-cli}/bin/tshark";
            capinfos = "${pkgs.wireshark-cli}/bin/capinfos";
            browser = "${pkgs.google-chrome}/bin/google-chrome-stable";
          };
          versions = {
            mitmproxy = pkgs.mitmproxy.version;
            wireshark = pkgs.wireshark-cli.version;
            browser = pkgs.google-chrome.version;
          };
        }
        {
          id = "native";
          skill = "native-analysis";
          tools = {
            rea = "${reaTools.cli}/bin/rea";
            ghidra = "${reaTools.ghidra}/lib/ghidra/support/analyzeHeadless";
          };
          versions = {
            ghidra = reaTools.ghidra.version;
          };
        }
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
        {
          id = "browser";
          skill = "re-browser";
          tools = {
            cli = "${chromeDevtools}/bin/chrome-devtools";
            browser = "${pkgs.google-chrome}/bin/google-chrome-stable";
          };
          versions = {
            cli = chromeDevtools.version;
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
  # Pin the agent's shell/evidence utilities, not just its analysis engines.
  runtimeTools = androidTools.packages ++ [
    pkgs.bash
    pkgs.coreutils
    pkgs.procps
    pkgs.ripgrep
    pkgs.jq
    pkgs.file
    pkgs.binutils
    pkgs.gnugrep
    pkgs.gnused
  ];
  launcher = pkgs.writeShellScriptBin "pi-re" ''
    export PI_RE_CONFIG=${runtime}
    # Child Bash must resolve this exact launcher, including before activation.
    export PATH="$(${pkgs.coreutils}/bin/dirname "$(${pkgs.coreutils}/bin/readlink -f "$0")")":${lib.makeBinPath runtimeTools}:"$PATH"
    exec ${python} ${resources}/lib/pi-re/launcher.py "$@"
  '';
in
{
  imports = [ ../pi-base ];
  home.packages = [ launcher ];
  # Archive originals and merge compatible missing entries privately, outside the store.
  home.activation.initializePiRe = lib.hm.dag.entryAfter [ "initializePi" ] ''
    if [ -v DRY_RUN ]; then
      echo "Would migrate legacy RE copies to the shared live Pi login/settings"
    else
      ${python} ${resources}/lib/pi-re/initialize.py \
        --agent-dir ${lib.escapeShellArg "${config.xdg.dataHome}/pi-re/agent"} \
        --state-dir ${lib.escapeShellArg "${config.xdg.stateHome}/pi-re"} \
        --source-agent-dir ${lib.escapeShellArg "${config.home.homeDirectory}/.pi/agent"}
    fi
  '';
}
