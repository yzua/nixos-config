#!/usr/bin/env python3
"""Boot-scoped system CA overlay for the owned API35 non-Play emulator only."""

import hashlib
import re
import shlex
import subprocess
from pathlib import Path

from android import LabError, read_json, safe_path, write_json

CERTS = "/apex/com.android.conscrypt/cacerts"


class SystemCA:
    def __init__(self, lab, openssl):
        self.lab = lab
        self.openssl = openssl
        self.metadata = safe_path(lab.state / "system-ca.json")

    def shell(self, args, timeout=15):
        code, output = self.lab.adb(["shell", *args], timeout)
        if code:
            raise LabError("Owned emulator system-CA operation failed")
        return output.strip()

    def script(self, source):
        return self.shell(["sh", "-c", shlex.quote("set -eu; " + source)], 30)

    def install(self, certificate):
        self.lab.device_identity()
        if (
            self.shell(["id", "-u"]) != "0"
            or self.shell(["getprop", "ro.build.version.sdk"]) != "35"
        ):
            raise LabError("System CA installation requires the owned rooted API35 lab")
        certificate = Path(certificate)
        if not certificate.is_file() or certificate.stat().st_size > 65536:
            raise LabError("Expected a bounded public CA certificate")
        content = certificate.read_bytes()
        if b"PRIVATE KEY" in content or b"-----BEGIN CERTIFICATE-----" not in content:
            raise LabError("Only the public CA certificate can be deployed to Android")
        try:
            result = subprocess.run(
                [self.openssl, "x509", "-in", str(certificate), "-subject_hash_old", "-noout"],
                text=True,
                capture_output=True,
                timeout=5,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise LabError("Cannot verify public CA subject hash") from error
        subject = result.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{8}", subject):
            raise LabError("Invalid public CA subject hash")
        digest = hashlib.sha256(content).hexdigest()
        boot = self.shell(["cat", "/proc/sys/kernel/random/boot_id"])
        token = self.lab.owner()["token"]
        if not re.fullmatch(r"[0-9a-f]{32}", token) or not re.fullmatch(r"[0-9a-f-]{36}", boot):
            raise LabError("Invalid selected lab boot/ownership identity")
        if self.metadata.exists():
            previous = read_json(self.metadata)
            if previous.get("owner") == token and previous.get("boot") == boot:
                if previous.get("digest") != digest:
                    raise LabError("CA changed during this guest boot; restart the owned emulator")
                filename = previous.get("filename", "")
                if not re.fullmatch(r"[0-9a-f]{8}\.[0-9]+", filename):
                    raise LabError("Invalid recorded CA filename")
                actual = self.shell(["sha256sum", CERTS + "/" + filename]).split()[0]
                if actual != digest:
                    raise LabError("Recorded system CA overlay changed; restart the owned emulator")
                zygotes = self.shell(["pidof", "zygote64", "zygote"]).split()
                if not zygotes or any(not pid.isdigit() for pid in zygotes):
                    raise LabError("Cannot verify current zygote mount namespaces")
                for pid in zygotes:
                    actual = self.shell(
                        ["nsenter", "-t", pid, "-m", "--", "sha256sum", CERTS + "/" + filename]
                    ).split()[0]
                    if actual != digest:
                        raise LabError(
                            "Zygote system CA overlay changed; restart the owned emulator"
                        )
                return {
                    "status": "ok",
                    "systemCA": "installed",
                    "reused": True,
                    "restartExistingApps": True,
                    "subjectHash": subject,
                }
        remote = f"/data/local/tmp/pi-re-ca-{token[:12]}-{boot[:8]}"
        # Files are public certificates, never the MITM private signing key. A
        # fresh per-boot directory avoids stacked overlays and foreign deletion.
        self.script(
            f"test ! -e {remote}; mkdir -m 755 {remote}; mkdir -m 755 {remote}/cacerts; "
            f"cp -a {CERTS}/. {remote}/cacerts/"
        )
        index = 0
        while True:
            filename = f"{subject}.{index}"
            code, _ = self.lab.adb(["shell", "test", "-e", f"{remote}/cacerts/{filename}"])
            if code:
                break
            index += 1
            if index > 20:
                raise LabError("Unexpected system CA subject collision count")
        code, _ = self.lab.adb(["push", str(certificate), f"{remote}/cacerts/{filename}"], 30)
        if code:
            raise LabError("Public system CA deployment failed")
        self.script(
            f"chown -R 0:0 {remote}/cacerts; chmod 755 {remote}/cacerts; "
            f"chmod 644 {remote}/cacerts/*; chcon -R u:object_r:system_file:s0 {remote}/cacerts; "
            f"mount --bind {remote}/cacerts {CERTS}"
        )
        # Android14+ Conscrypt lives in APEX. Zygote has its own mount namespace;
        # changing only adbd/init's view does not teach newly spawned apps trust.
        zygotes = self.shell(["pidof", "zygote64", "zygote"]).split()
        if not zygotes or any(not pid.isdigit() for pid in zygotes):
            raise LabError("Cannot select the lab's zygote mount namespaces")
        for pid in zygotes:
            self.shell(
                ["nsenter", "-t", pid, "-m", "--", "mount", "--bind", remote + "/cacerts", CERTS]
            )
        actual = self.shell(["sha256sum", CERTS + "/" + filename]).split()[0]
        if actual != digest:
            raise LabError("System CA overlay verification failed")
        write_json(
            self.metadata,
            {
                "version": 1,
                "owner": token,
                "boot": boot,
                "digest": digest,
                "filename": filename,
                "remote": remote,
            },
        )
        return {
            "status": "ok",
            "systemCA": "installed",
            "reused": False,
            "restartExistingApps": True,
            "subjectHash": subject,
        }
