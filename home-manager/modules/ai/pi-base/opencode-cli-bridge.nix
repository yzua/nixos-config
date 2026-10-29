# Pin the official-CLI Pi bridge and isolate/serialize its OpenCode subprocesses.
{ aiPackages, pkgs }:
let
  cli = pkgs.writeShellScript "pi-opencode-cli" ''
    set -euo pipefail
    umask 077
    state="''${XDG_STATE_HOME:-$HOME/.local/state}/pi-opencode-cli"
    ${pkgs.coreutils}/bin/mkdir -p "$state"/{home,config,data,cache,state,tmp}
    # Concurrent standalone startup/session deletion races SQLite migrations.
    # Keep the lock in the caller's namespace before replacing the child env.
    exec ${pkgs.util-linux}/bin/flock --no-fork "$state/cli.lock" \
      ${pkgs.coreutils}/bin/env -i \
      PATH=${
        pkgs.lib.makeBinPath [
          pkgs.coreutils
          pkgs.git
          pkgs.bash
          pkgs.nodejs_24
        ]
      } \
      HOME="$state/home" \
      XDG_CONFIG_HOME="$state/config" \
      XDG_DATA_HOME="$state/data" \
      XDG_STATE_HOME="$state/state" \
      XDG_CACHE_HOME="$state/cache" \
      TMPDIR="$state/tmp" \
      PWD="$PWD" \
      LANG=C.UTF-8 \
      SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt \
      OPENCODE_CONFIG_DIR="''${PI_OPENCODE_BRIDGE_AGENT_DIR:-$state/config/opencode}" \
      OPENCODE_DISABLE_UPDATE_CHECK=1 \
      OPENCODE_DISABLE_AUTOUPDATE=1 \
      ${aiPackages.opencode2}/bin/opencode2 "$@"
  '';
in
pkgs.stdenvNoCC.mkDerivation {
  pname = "pi-opencode-cli-bridge";
  version = "0.2.14";
  src = pkgs.fetchzip {
    url = "https://github.com/Gybra/pi-opencode-cli-bridge/archive/0366a962dbcd729220cd4771b30d2d48c63cd686.tar.gz";
    hash = "sha256-hLM04FbxhgHlVTPm6zmp2kZwBeWgJ8VsPe7OJ6YEWaM=";
  };
  dontBuild = true;
  patches = [
    ./opencode-cli-tool-envelope.patch
    ./opencode-cli-thinking.patch
  ];
  postPatch = ''
    # Preserve the upstream provider/protocol; only choose the managed executable.
    substituteInPlace src/cli.ts \
      --replace-fail 'return "opencode";' 'return "${cli}";' \
      --replace-fail 'env: { ...process.env, OPENCODE_DISABLE_UPDATE_CHECK: "1" },' \
        'env: { ...process.env, PI_OPENCODE_BRIDGE_AGENT_DIR: "", OPENCODE_DISABLE_UPDATE_CHECK: "1" },'
    # Only an inference turn supplies its generated guard directory. Discovery
    # and cleanup clear the private handoff instead of loading ambient config.
    substituteInPlace src/stream.ts \
      --replace-fail 'OPENCODE_CONFIG_DIR: join(sessionDir, ".opencode"),' \
        'PI_OPENCODE_BRIDGE_AGENT_DIR: join(sessionDir, ".opencode"),'
  '';
  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -r src "$out/vendor"
    cp README.md SECURITY.md LICENSE "$out/"
    find "$out/vendor" -name '*.test.ts' -delete
    cp ${./extensions/opencode-cli/index.ts} "$out/index.ts"
    runHook postInstall
  '';
  passthru = { inherit cli; };
  meta = {
    description = "Pi provider backed by the real OpenCode CLI";
    homepage = "https://github.com/Gybra/pi-opencode-cli-bridge";
    license = pkgs.lib.licenses.mit;
  };
}
