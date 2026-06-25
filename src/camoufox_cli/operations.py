"""Non-UI logic: transport, daemon lifecycle, and system provisioning.

This module is deliberately free of any CLI/UI framework import. ``cli.py``
imports it as ``from . import operations as ops`` and calls everything as
``ops.*`` so tests can monkeypatch the transport entrypoints at call time.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time

from .models import Command, Response, command_adapter, response_adapter

SOCKET_PREFIX = "/tmp/camoufox-cli-"
PROFILES_DIR = os.path.expanduser("~/.camoufox-cli/profiles")


class ResponseError(Exception):
    """Raised when a failure occurs *after* the command was transmitted.

    The daemon may already have executed the (possibly non-idempotent) action,
    so callers MUST NOT retry on this error.
    """

    def __init__(self, cause: Exception):
        super().__init__(str(cause))
        self.cause: Exception = cause


def get_socket_path(session: str) -> str:
    return f"{SOCKET_PREFIX}{session}.sock"


def get_log_path(session: str) -> str:
    return f"{SOCKET_PREFIX}{session}.log"


def send_command(sock_path: str, command: Command) -> Response:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall(command_adapter.dump_json(command) + b"\n")
    s.shutdown(socket.SHUT_WR)
    # Past this point the command is on the wire; any failure reading the
    # reply is a ResponseError, never a retryable connect-phase error.
    try:
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        return response_adapter.validate_json(data)
    except Exception as e:
        raise ResponseError(e) from e
    finally:
        s.close()


def spawn_daemon(
    session: str,
    headed: bool,
    timeout: int,
    persistent: str | None,
    proxy: str | None = None,
    geoip: bool = True,
    locale: str | None = None,
    clone_from: str | None = None,
) -> None:
    cmd = [
        sys.executable,
        "-m",
        "camoufox_cli",
        "--session",
        session,
        "--timeout",
        str(timeout),
    ]
    if headed:
        cmd.append("--headed")
    if persistent:
        cmd.extend(["--persistent", persistent])
    if proxy:
        cmd.extend(["--proxy", proxy])
    if not geoip:
        cmd.append("--no-geoip")
    if locale:
        cmd.extend(["--locale", locale])
    if clone_from:
        cmd.extend(["--clone-from", clone_from])

    log_path = get_log_path(session)
    with open(log_path, "ab", buffering=0) as log_file:
        _ = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    sock_path = get_socket_path(session)
    for _ in range(50):
        if os.path.exists(sock_path):
            return
        time.sleep(0.1)

    print(
        f"Error: Daemon did not start within 5 seconds; see {log_path}", file=sys.stderr
    )
    sys.exit(1)


def ensure_daemon(
    session: str,
    headed: bool,
    timeout: int,
    persistent: str | None,
    proxy: str | None = None,
    geoip: bool = True,
    locale: str | None = None,
    clone_from: str | None = None,
) -> None:
    sock_path = get_socket_path(session)
    if os.path.exists(sock_path):
        # Verify daemon is actually alive by trying to connect
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(sock_path)
            s.close()
            return
        except (ConnectionRefusedError, OSError):
            # Stale socket from a dead daemon — clean up
            with contextlib.suppress(FileNotFoundError):
                os.unlink(sock_path)
    spawn_daemon(session, headed, timeout, persistent, proxy, geoip, locale, clone_from)


def list_sessions() -> list[str]:
    sessions: list[str] = []
    try:
        for name in os.listdir("/tmp"):
            if name.startswith("camoufox-cli-") and name.endswith(".sock"):
                sessions.append(name[len("camoufox-cli-") : -len(".sock")])
    except OSError:
        pass
    sessions.sort()
    return sessions


def get_profile_path(session: str) -> str:
    return os.path.join(PROFILES_DIR, session)


def list_persistent_sessions() -> list[str]:
    profiles: list[str] = []
    try:
        for name in os.listdir(PROFILES_DIR):
            if os.path.isdir(os.path.join(PROFILES_DIR, name)):
                profiles.append(name)
    except OSError:
        pass
    profiles.sort()
    return profiles


def install_browser(with_deps: bool) -> None:
    print("[camoufox-cli] Downloading browser...", file=sys.stderr)
    from camoufox.pkgman import CamoufoxFetcher

    fetcher = CamoufoxFetcher()
    fetcher.install()
    print("[camoufox-cli] Browser installed.", file=sys.stderr)
    if with_deps:
        _install_system_deps()


def close_all_sessions() -> list[tuple[str, str | None]]:
    """Send ``close`` to every active session.

    Returns ``(session, error-or-None)`` per session.
    """
    from .models import CloseCommand, CloseParams

    results: list[tuple[str, str | None]] = []
    for session in list_sessions():
        try:
            _ = send_command(
                get_socket_path(session), CloseCommand(id="r1", params=CloseParams())
            )
            results.append((session, None))
        except Exception as e:  # transport/daemon failure is per-session, keep going
            results.append((session, str(e)))
    return results


_APT_DEPS = [
    "libxcb-shm0",
    "libx11-xcb1",
    "libx11-6",
    "libxcb1",
    "libxext6",
    "libxrandr2",
    "libxcomposite1",
    "libxcursor1",
    "libxdamage1",
    "libxfixes3",
    "libxi6",
    "libgtk-3-0",
    "libpangocairo-1.0-0",
    "libpango-1.0-0",
    "libatk1.0-0",
    "libcairo-gobject2",
    "libcairo2",
    "libgdk-pixbuf-2.0-0",
    "libxrender1",
    "libfreetype6",
    "libfontconfig1",
    "libdbus-1-3",
    "libnss3",
    "libnspr4",
    "libatk-bridge2.0-0",
    "libdrm2",
    "libxkbcommon0",
    "libatspi2.0-0",
    "libcups2",
    "libxshmfence1",
    "libgbm1",
]

_DNF_DEPS = [
    "nss",
    "nspr",
    "atk",
    "at-spi2-atk",
    "cups-libs",
    "libdrm",
    "libXcomposite",
    "libXdamage",
    "libXrandr",
    "mesa-libgbm",
    "pango",
    "alsa-lib",
    "libxkbcommon",
    "libxcb",
    "libX11-xcb",
    "libX11",
    "libXext",
    "libXcursor",
    "libXfixes",
    "libXi",
    "gtk3",
    "cairo-gobject",
]

_YUM_DEPS = [
    "nss",
    "nspr",
    "atk",
    "at-spi2-atk",
    "cups-libs",
    "libdrm",
    "libXcomposite",
    "libXdamage",
    "libXrandr",
    "mesa-libgbm",
    "pango",
    "alsa-lib",
    "libxkbcommon",
]


def _resolve_apt_libasound() -> str:
    """Newer Debian/Ubuntu renamed libasound2 to libasound2t64."""
    result = subprocess.run(
        ["dpkg", "-l", "libasound2t64"],
        capture_output=True,
    )
    return "libasound2t64" if result.returncode == 0 else "libasound2"


def _install_system_deps() -> None:
    import platform
    import shutil

    if platform.system() != "Linux":
        print(
            "[camoufox-cli] System dependencies are only needed on Linux, skipping.",
            file=sys.stderr,
        )
        return

    print("[camoufox-cli] Installing system dependencies...", file=sys.stderr)

    if shutil.which("apt-get"):
        deps = [*_APT_DEPS, _resolve_apt_libasound()]
        _ = subprocess.run(["sudo", "apt-get", "update", "-y"], check=True)
        _ = subprocess.run(["sudo", "apt-get", "install", "-y", *deps], check=True)
    elif shutil.which("dnf"):
        _ = subprocess.run(["sudo", "dnf", "install", "-y", *_DNF_DEPS], check=True)
    elif shutil.which("yum"):
        _ = subprocess.run(["sudo", "yum", "install", "-y", *_YUM_DEPS], check=True)
    else:
        print(
            "[camoufox-cli] Could not detect a supported package manager "
            + "(apt-get, dnf, yum).",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[camoufox-cli] System dependencies installed.", file=sys.stderr)
