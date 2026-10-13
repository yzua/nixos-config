# Build immutable Pi extensions once; each profile explicitly selects what it loads.
{ pkgs, setup }:
let
  searchConfig = pkgs.writeText "pi-web-search-config.json" (builtins.toJSON setup.pi.webSearch);
in
pkgs.buildNpmPackage {
  pname = "pi-personal-extensions";
  version = "local";
  src = ./extensions/web-fetch;
  npmDepsHash = "sha256-Rbdj6jd25Urxr1wJj1Vl7mefv1IKu5zQhHgt6dOEqaU=";
  npmFlags = [ "--ignore-scripts" ];
  dontNpmBuild = true;
  installPhase = ''
    runHook preInstall
    resources="$out/lib/pi-config"
    mkdir -p "$resources/web-fetch" "$resources/prompt-snippets"
    cp -r node_modules "$resources/web-fetch/"
    cp index.ts package.json "$resources/web-fetch/"
    cp ${./extensions/ask-user-question.ts} "$resources/ask-user-question.ts"
    cp ${./extensions/network-diagnostics.ts} "$resources/network-diagnostics.ts"
    cp ${./extensions/upstream-retry.ts} "$resources/upstream-retry.ts"
    cp -r ${./extensions/prompt-snippets}/. "$resources/prompt-snippets/"
    cp -r ${./extensions/web-search} "$resources/web-search"
    chmod u+w "$resources/web-search"
    cp ${searchConfig} "$resources/web-search/config.json"
    cp -r ${./extensions/interactive-subagents} "$resources/interactive-subagents"
    runHook postInstall
  '';
}
