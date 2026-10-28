# Repack the official REA-compatible Node binary without compiling Node/V8.
{ pkgs }:
pkgs.stdenvNoCC.mkDerivation {
  pname = "nodejs-rea-bin";
  version = "24.22.1";
  src = pkgs.fetchurl {
    url = "https://nodejs.org/dist/v24.22.1/node-v24.22.1-linux-x64.tar.xz";
    # Verified against the signed upstream SHASUMS256.txt release manifest.
    hash = "sha256-bBcqmrZxj3uAH7WnvUhq8u5eMnWAhqBLhPzOKqdwleY=";
  };
  nativeBuildInputs = [ pkgs.autoPatchelfHook ];
  buildInputs = [ (pkgs.lib.getLib pkgs.stdenv.cc.cc) ];
  dontConfigure = true;
  dontBuild = true;
  dontStrip = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -r bin include lib share LICENSE CHANGELOG.md README.md "$out/"
    PATH="$out/bin:$PATH" patchShebangs --build "$out/lib/node_modules"
    runHook postInstall
  '';
  meta = {
    description = "Official Node.js runtime for pinned REA";
    homepage = "https://nodejs.org/";
    license = pkgs.lib.licenses.mit;
    platforms = [ "x86_64-linux" ];
    mainProgram = "node";
  };
}
