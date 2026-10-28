# Package the official Agent Reach release without its mutable upstream installer.
{
  lib,
  fetchurl,
  callPackage,
  google-chrome,
  nodejs,
  python3Packages,
}:

let
  opencli = callPackage ./opencli.nix { };
in
python3Packages.buildPythonApplication rec {
  pname = "agent-reach";
  version = "1.6.0";
  pyproject = true;

  src = fetchurl {
    url = "https://github.com/Panniantong/Agent-Reach/releases/download/v${version}/agent_reach-${version}.tar.gz";
    hash = "sha256-iX81qJEsvmKUeX0TBaNiJJJWCbtMUHQqVWatYwW0cH0=";
  };

  # Reuse managed binaries/extensions and require explicit session import.
  postPatch = ''
    substituteInPlace agent_reach/runtime/browser.py \
      --replace-fail 'return browser_root() / "extension"' 'return Path("${opencli.extension}")' \
      --replace-fail '    selected = chrome_binary()' \
        '    selected = "${google-chrome}/bin/google-chrome-stable"' \
      --replace-fail $'    if selected and _load_state().get("backend") and not retry_cloak:\n        return selected' \
        $'    if selected:\n        update_state(backend="chrome", executable=selected, launcher_python=None)\n        return selected'
    substituteInPlace agent_reach/runtime/session_reuse.py \
      --replace-fail '        cookies, source = _source_cookies(channel, site_domains(ch))' \
        $'        if not force:\n            return {"source": "explicit_import_only", "copied_cookies": 0}\n        cookies, source = _source_cookies(channel, site_domains(ch))'
    cp ${./test-managed.py} tests/test_nix_managed.py
  '';

  makeWrapperArgs = [
    "--prefix PATH : ${
      lib.makeBinPath [
        opencli
        google-chrome
        nodejs
      ]
    }"
  ];

  build-system = [ python3Packages.hatchling ];
  dependencies = with python3Packages; [
    requests
    loguru
    pyyaml
    yt-dlp
  ];

  nativeCheckInputs = [ python3Packages.pytestCheckHook ];
  # These tests are offline and do not install tools or inspect real accounts.
  pytestFlags = [
    "tests/test_channels.py"
    "tests/test_reddit_channel.py"
    "tests/test_url_security.py"
    "tests/test_nix_managed.py"
  ];
  pythonImportsCheck = [ "agent_reach" ];

  passthru = { inherit opencli; };

  meta = {
    description = "Search and read internet platforms from AI agents";
    homepage = "https://github.com/Panniantong/Agent-Reach";
    license = lib.licenses.mit;
    mainProgram = "agent-reach";
  };
}
