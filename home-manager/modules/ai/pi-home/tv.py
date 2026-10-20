#!/usr/bin/env python3
"""On-demand, bounded Samsung TV controls. No discovery, service, debug or root API."""

import argparse
import contextlib
import fcntl
import ipaddress
import json
import logging
import os
import signal
import ssl
import stat
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

KEYS = {
    "up": "KEY_UP",
    "down": "KEY_DOWN",
    "left": "KEY_LEFT",
    "right": "KEY_RIGHT",
    "enter": "KEY_ENTER",
    "back": "KEY_RETURN",
    "home": "KEY_HOME",
    "volume-up": "KEY_VOLUP",
    "volume-down": "KEY_VOLDOWN",
    "mute": "KEY_MUTE",
    "play": "KEY_PLAY",
    "pause": "KEY_PAUSE",
    "stop": "KEY_STOP",
    "power-off": "KEY_POWEROFF",
}


class ControlError(ValueError):
    """Only locally authored, credential-free messages may reach the CLI."""


def safe_path(path, directory=False):
    if not path.is_absolute():
        raise ControlError("TV state paths must be absolute")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ControlError("TV state paths must not contain symlinks")
    if path.exists():
        info = path.stat()
        valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not valid_type or info.st_uid != os.getuid() or (not directory and info.st_nlink != 1):
            raise ControlError("TV state must be caller-owned, regular and single-link")


def token_path(environment):
    home = Path(environment["HOME"])
    state = Path(environment.get("XDG_STATE_HOME") or home / ".local/state")
    return state / "samsung-tv-remote/token"


def save_token(path, value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ControlError("TV returned an invalid pairing token")
    safe_path(path)
    fd, temporary = tempfile.mkstemp(prefix=".token.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(value.strip())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def device_info(host):
    # Bypass HTTP proxies for this configured LAN endpoint; never follow a TV redirect.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(f"http://{host}:8001/api/v2/", timeout=8) as response:
        value = json.loads(response.read(65537))
    device = value.get("device", {})
    return {key: device[key] for key in ("name", "modelName", "type") if key in device}


def volume_request(host, action, level=None):
    """Only RenderingControl Get/SetVolume, on the configured TV; no discovery/replay."""
    if action not in ("GetVolume", "SetVolume"):
        raise ControlError("Unsupported volume operation")
    if action == "SetVolume" and (type(level) is not int or not 0 <= level <= 100):
        raise ControlError("Volume must be an integer from 0 to 100")
    desired = f"<DesiredVolume>{level}</DesiredVolume>" if action == "SetVolume" else ""
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
        f'<u:{action} xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
        f"<InstanceID>0</InstanceID><Channel>Master</Channel>{desired}"
        f"</u:{action}></s:Body></s:Envelope>"
    ).encode()
    request = urllib.request.Request(
        f"http://{host}:9197/upnp/control/RenderingControl1",
        data=body,
        headers={
            "SOAPAction": f'"urn:schemas-upnp-org:service:RenderingControl:1#{action}"',
            "Content-Type": "text/xml; charset=utf-8",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=8) as response:
        data = response.read(65537)
    if len(data) > 65536:
        raise ControlError("Invalid TV volume response")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ControlError("Invalid TV volume response") from error
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ControlError("Invalid TV volume response")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ControlError("Invalid TV volume response") from error
    tags = [node.tag.rsplit("}", 1)[-1] for node in root.iter()]
    if "Fault" in tags or f"{action}Response" not in tags:
        raise ControlError("TV rejected the volume request")
    if action == "GetVolume":
        values = [
            node.text for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "CurrentVolume"
        ]
        if (
            len(values) != 1
            or not values[0]
            or not values[0].isdecimal()
            or not 0 <= int(values[0]) <= 100
        ):
            raise ControlError("Invalid TV volume response")
        return int(values[0])
    return None


@contextlib.contextmanager
def operation_deadline(seconds=25):
    """The CLI is a dedicated main-thread process; bound the whole operation, not idle reads."""

    def expired(_signum, _frame):
        raise ControlError("TV operation deadline reached; outcome uncertain. No automatic retry.")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def scoped_remote(base_class, connector):
    """Keep upstream command encoding, but own the no-redirect authorization handshake."""

    class Remote(base_class):
        def open(self):
            if self.connection:
                return self.connection
            self.connection = connector(
                self._format_websocket_url(self.endpoint),
                timeout=self.timeout,
                sslopt={"cert_reqs": ssl.CERT_NONE},
                redirect_limit=0,
                http_no_proxy=[self.host],
                connection="Connection: Upgrade",
            )
            if self.connection.getstatus() != 101:
                raise ControlError(
                    "TV refused the configured WebSocket endpoint; redirects are disabled"
                )
            while True:
                message = self.connection.recv()
                if not message or len(message) > 65536:
                    raise ControlError("Invalid TV authorization response")
                response = json.loads(message)
                event = response.get("event")
                if event == "ms.channel.connect":
                    self._check_for_token(response)
                    return self.connection
                if event in ("ms.channel.unauthorized", "ms.channel.timeOut", "ms.error"):
                    raise ControlError("TV did not authorize this connection")
                # Other startup notifications do not extend the overall deadline.

        def close(self):
            connection, self.connection = self.connection, None
            if connection:
                connection.shutdown()  # No unbounded close-handshake wait or receive thread.

    return Remote


def run(config, args, environment=None, factory=None):
    environment = os.environ if environment is None else environment
    host = config["host"]
    address = ipaddress.ip_address(host)
    if not any(
        address in ipaddress.ip_network(network)
        for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    ):
        raise ControlError("Configure a private IPv4 LAN TV address in setup.pi.home.samsung")
    # Validate the requested operation before reading credentials or opening any socket.
    if args.command == "key" and args.key not in KEYS:
        raise ControlError("Unsupported remote key")
    if args.command == "launch" and args.app not in config.get("apps", {}):
        raise ControlError("Only configured applications may be launched")
    volume_level = args.level if args.command == "volume" else None
    if volume_level is not None and (type(volume_level) is not int or not 0 <= volume_level <= 100):
        raise ControlError("Volume must be an integer from 0 to 100")
    if (args.command in ("key", "launch") or volume_level is not None) and not args.execute:
        raise ControlError("Device actions require --execute and an explicit user request")
    if args.command == "info":
        return device_info(host)
    if args.command == "volume" and volume_level is None:
        if args.execute:
            raise ControlError("Select a volume level before using --execute")
        return {
            "status": "read",
            "operation": "volume",
            "volume": volume_request(host, "GetVolume"),
        }
    token = token_path(environment)
    safe_path(token.parent, directory=True)
    token.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(token.parent, 0o700)
    safe_path(token)
    lock = token.parent / "control.lock"
    safe_path(lock)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ControlError("Another on-demand TV operation is active") from error
        if token.exists() and token.stat().st_size > 4096:
            raise ControlError("Invalid saved pairing token; preserve it for review")
        current = token.read_text().strip() if token.exists() else None
        if current is not None:
            os.chmod(token, 0o600)
        if args.command != "connect" and not current:
            raise ControlError("Pair first with pi-home tv connect; it sends no buttons")
        if factory is None:
            import websocket
            from samsungtvws import SamsungTVWS

            factory = scoped_remote(SamsungTVWS, websocket.create_connection)
        remote = factory(
            host=host, port=8002, token=current, timeout=20, name="Pi Home", key_press_delay=0.3
        )
        try:
            # Samsung uses a self-signed certificate on this configured LAN WebSocket.
            # The library scopes verification relaxation to this socket, not global TLS.
            remote.open()
            if remote.token:
                save_token(token, remote.token)
            if args.command == "volume":
                before = volume_request(host, "GetVolume")
                if before != volume_level:
                    volume_request(host, "SetVolume", volume_level)
                    after = volume_request(host, "GetVolume")
                else:
                    after = before
                if after != volume_level:
                    raise ControlError(
                        "Volume command sent, but read-back did not match; no automatic retry"
                    )
                return {
                    "status": "verified",
                    "operation": "volume",
                    "previous": before,
                    "volume": after,
                }
            if args.command == "key":
                remote.send_key(KEYS[args.key])
            elif args.command == "launch":
                remote.run_app(config["apps"][args.app])
            return {
                "status": "authorized" if args.command == "connect" else "sent",
                "operation": args.command,
                "observation": "No screen or UI state available",
            }
        finally:
            remote.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info", help="Read basic TV identity, without pairing or buttons")
    commands.add_parser(
        "connect", help="Authorize and close; no buttons (may show a pairing prompt)"
    )
    key = commands.add_parser("key", help="Send exactly one allowed button")
    key.add_argument("key", choices=sorted(KEYS))
    key.add_argument("--execute", action="store_true")
    app = commands.add_parser(
        "launch", help="Launch a configured app, without debug/reinstallation"
    )
    app.add_argument("app")
    app.add_argument("--execute", action="store_true")
    volume = commands.add_parser(
        "volume", help="Read volume, or set an exact 0-100 level and verify it"
    )
    volume.add_argument("level", nargs="?", type=int, choices=range(101))
    volume.add_argument("--execute", action="store_true")
    # The managed launcher supplies only the non-secret device facts.
    config = json.loads(Path(sys.argv[1]).read_text())
    args = parser.parse_args(sys.argv[2:])
    os.umask(0o077)
    logging.disable(logging.CRITICAL)  # Upstream debug/errors can contain token-bearing URLs.
    # Keep this local socket out of inherited HTTP proxies (both spellings are used upstream).
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = config["host"]
    try:
        with operation_deadline():
            result = run(config, args)
    except ControlError as error:
        parser.exit(1, f"TV control: {error}\n")
    except Exception:
        # Never print upstream exception bodies, URLs, token values or raw TV events.
        parser.exit(
            1,
            "TV control failed; check TV power, LAN sharing and pairing permission. No automatic retry.\n",
        )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
