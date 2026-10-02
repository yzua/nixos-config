"""mitmdump 12.2.3 discovery or optional exact-host scope gate; no flow logging.

The adapter uses lazy connections and disables upstream certificate sniffing.
Only one explicitly approved fixture hostname may be routed to loopback. Its
original hostname remains SNI and the upstream certificate verification name.
"""

import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

from mitmproxy import ctx, exceptions, http

DENIED = "Host not approved for traffic capture"


def host_name(value):
    if not isinstance(value, str) or len(value) > 253:
        return None
    value = value.lower()
    if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", s) for s in value.split(".")):
        return None
    return value


class CaptureScope:
    def __init__(self):
        self.allowed = frozenset()
        self.capture_all = False
        self.fixture = None
        self.ready = None
        self.configured = False

    def load(self, loader):
        # Fail closed before load, and keep the run policy in memory thereafter.
        try:
            path = Path(os.environ["PI_RE_TRAFFIC_CONFIG"])
            if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
                raise ValueError()
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd) as stream:
                info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o400
                    or info.st_size > 16384
                ):
                    raise ValueError()
                config = json.load(stream)
            hosts = config["allowedHosts"]
            capture_all = config.get("captureAll", False)
            if (
                type(capture_all) is not bool
                or not isinstance(hosts, list)
                or len(hosts) > 128
                or (capture_all and hosts)
                or (not capture_all and not hosts)
            ):
                raise ValueError()
            allowed = frozenset(host_name(host) for host in hosts)
            if None in allowed:
                raise ValueError()
            fixture = config.get("fixture")
            if fixture is not None:
                host, port = host_name(fixture["host"]), fixture["port"]
                if (
                    host is None
                    or (not capture_all and host not in allowed)
                    or type(port) is not int
                    or not 1024 <= port <= 65535
                ):
                    raise ValueError()
                fixture = {"host": host, "port": port}
            ready = Path(config["readyFile"])
            if (
                not ready.is_absolute()
                or ready.parent != path.parent
                or ready.name != "ready.json"
                or not re.fullmatch(r"run-[0-9a-f]{32}", path.parent.name)
            ):
                raise ValueError()
            self.allowed, self.fixture, self.ready = allowed, fixture, ready
            self.capture_all = capture_all
            self.configured = True
        except (KeyError, TypeError, ValueError, OSError, UnicodeError) as exc:
            raise exceptions.OptionsError("Invalid private traffic scope configuration") from exc

    def running(self):
        if (
            not self.configured
            or ctx.options.connection_strategy != "lazy"
            or ctx.options.upstream_cert
            or ctx.options.ssl_insecure
        ):
            self.allowed = frozenset()
            self.capture_all = False
            self.configured = False
            raise exceptions.OptionsError(
                "Traffic requires lazy, verified upstream TLS without certificate sniffing"
            )
        # The adapter waits for this acknowledgement as well as its own listener
        # inode and CA. No traffic bodies, URLs, headers, auth or tool logs escape.
        fd = os.open(self.ready, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump({"configured": True, "version": 1}, stream)

    def deny(self, flow):
        flow.response = http.Response.make(403, DENIED.encode(), {"Content-Type": "text/plain"})

    def http_connect(self, flow):
        # CONNECT has its own hook and does not pass through requestheaders.
        if not self.capture_all or not self.configured:
            if host_name(flow.request.host) not in self.allowed:
                self.deny(flow)

    def requestheaders(self, flow):
        # Handles plain HTTP and decrypted requests inside approved CONNECTs.
        # Also reject an unapproved virtual Host authority on an approved route.
        if self.capture_all and self.configured:
            return
        if host_name(flow.request.host) not in self.allowed:
            self.deny(flow)
            return
        authority = flow.request.host_header
        if authority is not None:
            try:
                host = urlsplit("//" + authority).hostname
            except ValueError:
                host = None
            if host_name(host) not in self.allowed:
                self.deny(flow)

    def server_connect(self, data):
        # Last gate, covering non-HTTP CONNECT tunnels too. Setting server.error
        # aborts the connection before DNS/TCP upstream activity in mitmproxy.
        address = data.server.address
        host = host_name(address[0]) if address else None
        if (not self.capture_all or not self.configured) and host not in self.allowed:
            data.server.error = DENIED
            return
        sni = data.server.sni
        if not self.capture_all and sni is not None and host_name(sni) != host:
            data.server.error = DENIED
            return
        if self.fixture and host == self.fixture["host"]:
            data.server.sni = host
            data.server.address = ("127.0.0.1", self.fixture["port"])


addons = [CaptureScope()]
