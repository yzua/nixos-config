# Pin Agent Reach's tested OpenCLI browser adapter and preserve its daemon layout.
{
  lib,
  buildNpmPackage,
  fetchzip,
}:

buildNpmPackage {
  pname = "opencli";
  version = "1.8.7";
  src = fetchzip {
    url = "https://github.com/jackwener/OpenCLI/archive/87b60a36590c3e2a466c37266c3348d73d7f68fe.tar.gz";
    hash = "sha256-AHBfF+WnGLbd8fqhc1+7LIm9a0Xe7UQPZL4MQ3bZeuE=";
  };
  npmDepsHash = "sha256-IPI3buIo1ZDV7jvrtTWsxXGh+AJpXsgS/7sFv5rIOkE=";
  npmFlags = [ "--ignore-scripts" ];
  # Do not run upstream postinstall (daemon setup and mutable adapter downloads).
  makeCacheWritable = true;
  postInstall = ''
    # Agent Reach discovers the daemon relative to the executable's ancestors.
    ln -s "$out/lib/node_modules/@jackwener/opencli/dist" "$out/dist"
    ln -s "$out/lib/node_modules/@jackwener/opencli/package.json" "$out/package.json"
  '';
  passthru.extension = fetchzip {
    stripRoot = false;
    url = "https://github.com/jackwener/OpenCLI/releases/download/v1.8.7/opencli-extension-v1.0.23.zip";
    hash = "sha256-MQmyLkwuf18toeq4aS8I1o8ozm8bzV1z4zsvIw6kfLk=";
  };
  buildPhase = ''
    runHook preBuild
    npm run clean-dist
    npm run copy-yaml
    npm exec -- tsc --build
    chmod +x dist/src/main.js
    npm run build-manifest
    runHook postBuild
  '';

  meta = {
    description = "Browser-backed CLI adapters for internet platforms";
    homepage = "https://github.com/jackwener/OpenCLI";
    license = lib.licenses.asl20;
    mainProgram = "opencli";
  };
}
