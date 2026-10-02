#!/usr/bin/env python3
"""Build the owned fixture APK with supplied pinned SDK/JDK, never download tools."""

import argparse
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--jdk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Refusing to overwrite an existing APK")
    source = Path(__file__).parent
    tools = args.sdk_root / "build-tools/35.0.0"
    android = args.sdk_root / "platforms/android-35/android.jar"
    environment = os.environ.copy()
    environment["JAVA_HOME"] = str(args.jdk)
    environment["PATH"] = str(args.jdk / "bin") + os.pathsep + environment.get("PATH", "")

    def run(argv):
        subprocess.run([str(arg) for arg in argv], env=environment, check=True, timeout=60)

    # Temporary signing material is local, not in Git or any Nix-store output.
    with tempfile.TemporaryDirectory(prefix="pi-re-fixture-") as temporary:
        work = Path(temporary)
        classes = work / "classes"
        classes.mkdir()
        run(
            [
                args.jdk / "bin/javac",
                "--release",
                "8",
                "-classpath",
                android,
                "-d",
                classes,
                source / "MainActivity.java",
            ]
        )
        jar = work / "classes.jar"
        with zipfile.ZipFile(jar, "w") as archive:
            for path in classes.rglob("*.class"):
                archive.write(path, path.relative_to(classes))
        run([tools / "d8", "--lib", android, "--output", work, jar])
        apk = work / "unsigned.apk"
        run(
            [
                tools / "aapt2",
                "link",
                "-I",
                android,
                "--manifest",
                source / "AndroidManifest.xml",
                "-o",
                apk,
            ]
        )
        with zipfile.ZipFile(apk, "a") as archive:
            archive.write(work / "classes.dex", "classes.dex")
        aligned = work / "aligned.apk"
        run([tools / "zipalign", "-p", "4", apk, aligned])
        environment["PI_RE_FIXTURE_STORE_PASS"] = os.urandom(24).hex()
        key = work / "fixture.keystore"
        run(
            [
                args.jdk / "bin/keytool",
                "-genkeypair",
                "-keystore",
                key,
                "-alias",
                "fixture",
                "-storepass:env",
                "PI_RE_FIXTURE_STORE_PASS",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "1",
                "-dname",
                "CN=Owned Offline Fixture",
            ]
        )
        signed = work / "fixture.apk"
        run(
            [
                tools / "apksigner",
                "sign",
                "--ks",
                key,
                "--ks-pass",
                "env:PI_RE_FIXTURE_STORE_PASS",
                "--out",
                signed,
                aligned,
            ]
        )
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(signed, output)
        output.chmod(0o600)
        environment.pop("PI_RE_FIXTURE_STORE_PASS", None)
    print(output)


if __name__ == "__main__":
    main()
