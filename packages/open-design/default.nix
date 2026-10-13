# Build the local OpenDesign browser workspace and CLI from a pinned release.
{
  lib,
  stdenv,
  fetchFromGitHub,
  nodejs_24,
  pnpm,
  fetchPnpmDeps,
  pnpmConfigHook,
  python3,
  makeWrapper,
  git,
  bash,
  xdg-utils,
  poppler-utils,
  chromium,
  browser ? chromium,
}:
let
  # Use maintained pnpm rather than Nixpkgs's insecure pnpm 10.
  packageManager = pnpm;
  workspaces = [
    "@open-design/daemon..."
    "@open-design/web..."
    "@open-design/dsh-runtime..."
  ];
  patchPackageManager = ''
    ${lib.getExe python3} - <<'PY'
    import json
    import re
    from pathlib import Path
    path = Path("package.json")
    package = json.loads(path.read_text())
    package.pop("packageManager", None)
    package["engines"].pop("pnpm", None)
    # pnpm 11 reads overrides from the workspace rather than package.json.
    # Preserve the exact upstream locked dependency resolutions.
    settings = package.pop("pnpm")
    workspace = Path("pnpm-workspace.yaml")
    workspace.write_text(re.sub(
        r"(?m)^overrides:\n(?:[ \t]+.*\n)*",
        "overrides: " + json.dumps(settings["overrides"]) + "\n",
        workspace.read_text(),
    ))
    path.write_text(json.dumps(package, indent=2) + "\n")
    PY
  '';
in
stdenv.mkDerivation (finalAttrs: {
  pname = "open-design";
  version = "0.24.1";

  src = fetchFromGitHub {
    owner = "nexu-io";
    repo = "open-design";
    rev = "89e64d813bb1c7a11519b3f668f011f7017637d7";
    hash = "sha256-CJpr0JIww5XGgPqTDwaQlPBCB0Kz5GtOCOyKMfT9zyA=";
  };

  postPatch = patchPackageManager;
  pnpmDeps = fetchPnpmDeps {
    inherit (finalAttrs) pname version src;
    pnpm = packageManager;
    postPatch = patchPackageManager;
    pnpmWorkspaces = workspaces;
    fetcherVersion = 4;
    hash = "sha256-Ia08NsE+Ect/UGbxFjxjcraLFAZkWGvak9uYOB8O0uc=";
  };
  pnpmWorkspaces = workspaces;

  nativeBuildInputs = [
    nodejs_24
    packageManager
    pnpmConfigHook
    python3
    makeWrapper
  ];

  env = {
    npm_config_nodedir = "${nodejs_24}";
    npm_config_build_from_source = "true";
    NEXT_TELEMETRY_DISABLED = "1";
    ELECTRON_SKIP_BINARY_DOWNLOAD = "1";
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1";
    CI = "true";
  };

  buildPhase = ''
    runHook preBuild
    pnpm --filter '@open-design/daemon...' --filter '@open-design/web^...' \
      --filter '@open-design/dsh-runtime...' \
      --workspace-concurrency=2 --if-present run build
    pnpm --filter @open-design/web run build
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    root="$out/share/open-design"
    mkdir -p "$root/apps/daemon" "$root/apps/web" "$out/bin"
    # Keep workspace links intact. pnpm 11's legacy deploy needs unpinned
    # registry metadata even with --offline, so install the locked tree instead.
    cp -r node_modules packages "$root/"
    cp package.json "$root/"
    cp -r apps/daemon/{dist,bin,node_modules,package.json} "$root/apps/daemon/"
    cp -r apps/web/out "$root/apps/web/"
    # Root development-tool links are unused and their targets aren't shipped.
    rm "$root"/node_modules/@open-design/tools-{dev,pack,release,serve}
    # Install scripts are disabled throughout. Build only the required native
    # addons against Nix's Node headers, without fetching prebuilt binaries.
    for package in better-sqlite3 node-pty; do
      directory=$(readlink -f "$root/apps/daemon/node_modules/$package")
      (cd "$directory" && node ${nodejs_24}/lib/node_modules/npm/node_modules/node-gyp/bin/node-gyp.js rebuild)
    done
    cp -r skills design-templates design-systems craft prompt-templates \
      assets data plugins "$root/"
    # Reuse upstream's integrity-addressed companion bundler so setup doesn't
    # attempt to compile inside the immutable installed workspace.
    OD_NIX_RESOURCE_ROOT="$root" npm_execpath=${packageManager}/bin/pnpm pnpm exec tsx --eval '
      import { packBundledDshRuntime } from "./tools/pack/src/resources/index.ts";
      void packBundledDshRuntime({
        workspaceRoot: process.cwd(), resourceRoot: process.env.OD_NIX_RESOURCE_ROOT
      });
    '

    makeWrapper ${nodejs_24}/bin/node "$out/bin/open-design" \
      --add-flags "$root/apps/daemon/dist/cli.js" \
      --prefix PATH : ${
        lib.makeBinPath [
          nodejs_24
          git
          bash
          xdg-utils
          poppler-utils
        ]
      } \
      --set NODE_ENV production \
      --set-default HYPERFRAMES_BROWSER_PATH ${lib.getExe browser} \
      --run 'umask 077' \
      --run 'export OD_DATA_DIR="''${OD_DATA_DIR:-''${XDG_DATA_HOME:-$HOME/.local/share}/open-design}"' \
      --run 'export OD_BIND_HOST="''${OD_BIND_HOST:-127.0.0.1}"'
    runHook postInstall
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    "$out/bin/open-design" --help > /dev/null
    node - "$out/share/open-design/apps/daemon" <<'JS'
    const { createRequire } = require('node:module');
    const load = createRequire(process.argv[2] + '/package.json');
    const database = new (load('better-sqlite3'))(':memory:');
    database.exec('CREATE TABLE smoke(value INTEGER); INSERT INTO smoke VALUES (42)');
    database.close();
    load('node-pty');
    const fs = require('node:fs');
    const path = require('node:path');
    const crypto = require('node:crypto');
    const bundle = path.resolve(process.argv[2], '../../agent-runtimes/deepseek-harness');
    const manifest = JSON.parse(fs.readFileSync(path.join(bundle, 'manifest.json')));
    const digest = crypto.createHash('sha256')
      .update(fs.readFileSync(path.join(bundle, manifest.file))).digest('hex');
    if (digest !== manifest.sha256) throw new Error('Companion integrity check failed');
    JS
    runHook postInstallCheck
  '';

  meta = {
    description = "Local-first AI design workspace using your coding agents";
    homepage = "https://github.com/nexu-io/open-design";
    license = lib.licenses.asl20;
    platforms = lib.platforms.linux;
    mainProgram = "open-design";
  };
})
