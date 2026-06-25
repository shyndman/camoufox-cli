"""Unix socket server for the camoufox-cli daemon."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import socket
import sys
import tempfile
import threading
import time
from types import FrameType

from .browser import BrowserManager
from .commands import execute
from .models import OkResponse, Response, ResponseData
from .protocol import parse_command, serialize_response


class DaemonServer:
    def __init__(
        self,
        session: str = "default",
        headless: bool = True,
        timeout: int = 1800,
        persistent: str | None = None,
        proxy: str | None = None,
        geoip: bool = True,
        locale: str | None = None,
        clone_from: str | None = None,
    ):
        self.session: str = session
        self.headless: bool = headless
        self.timeout: int = timeout  # idle timeout in seconds
        self.socket_path: str = f"/tmp/camoufox-cli-{session}.sock"
        self.pid_path: str = f"/tmp/camoufox-cli-{session}.pid"
        self._clone_from: str | None = clone_from
        self._ephemeral_dir: str | None = (
            tempfile.mkdtemp(prefix="camoufox-cli-clone-") if clone_from else None
        )
        self.manager: BrowserManager = BrowserManager(
            persistent=self._ephemeral_dir or persistent,
            proxy=proxy,
            geoip=geoip,
            locale=locale,
        )
        self._server_socket: socket.socket | None = None
        self._last_activity: float = time.time()
        self._running: bool = False
        # Signature of the live tab set after the previous command, used to
        # inject the current tab list whenever the set of tabs changes.
        self._last_tab_sig: frozenset[int] | None = None

    def start(self) -> None:
        self._cleanup_stale()
        self._write_pid()
        self._running = True

        # Start idle timeout watchdog
        watchdog = threading.Thread(target=self._idle_watchdog, daemon=True)
        watchdog.start()

        # Set up signal handlers
        _ = signal.signal(signal.SIGTERM, self._handle_signal)
        _ = signal.signal(signal.SIGINT, self._handle_signal)

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self._server_socket.bind(self.socket_path)
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)  # allow periodic checks
            self._clone_profile()

            while self._running:
                try:
                    conn = self._server_socket.accept()[0]
                except TimeoutError:
                    continue
                except OSError:
                    break

                self._last_activity = time.time()
                try:
                    self._handle_connection(conn)
                except Exception as e:
                    print(f"[camoufox-cli] Connection error: {e}", file=sys.stderr)
                finally:
                    conn.close()
        finally:
            self._shutdown()

    def _clone_profile(self) -> None:
        """Copy the source persistent profile into the ephemeral dir so the
        session starts with the human's cookies/identity and writes nothing
        back."""
        if self._clone_from is None or self._ephemeral_dir is None:
            return
        # ponytail: copies the whole profile dir; if huge caches ever push the
        # copy past the client's socket-wait, exclude cache subdirs. Source is
        # read-only.
        _ = shutil.copytree(self._clone_from, self._ephemeral_dir, dirs_exist_ok=True)

    def _handle_connection(self, conn: socket.socket) -> None:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

        line = data.decode("utf-8").strip()
        if not line:
            return

        command = parse_command(line)

        # The daemon's own launch mode (from --headed) decides headless, not the
        # client, so it's applied inside execute().
        response = execute(self.manager, command, headless=self.headless)
        self._inject_tab_changes(response)
        conn.sendall(serialize_response(response))

        # If close command, shut down the daemon
        if command.get("action") == "close":
            self._running = False

    def _inject_tab_changes(self, response: Response) -> None:
        """Append the current tab list to a response when the tab set changed.

        Tabs can appear or disappear as a side effect of any command (e.g. a
        click opening a popup), so the daemon tracks the live tab set and
        surfaces the full list whenever it differs from the previous command.
        """
        if not isinstance(response, OkResponse) or not self.manager.is_running:
            return
        try:
            pages = self.manager.get_context().pages
        except RuntimeError:
            return
        sig = frozenset(id(p) for p in pages)
        if sig == self._last_tab_sig:
            return
        self._last_tab_sig = sig
        if response.data is None:
            response.data = ResponseData()
        if response.data.tabs is None:
            response.data.tabs = self.manager.get_tabs()

    def _idle_watchdog(self) -> None:
        while self._running:
            time.sleep(10)
            if time.time() - self._last_activity > self.timeout:
                print(
                    f"[camoufox-cli] Idle timeout ({self.timeout}s), shutting down",
                    file=sys.stderr,
                )
                self._running = False
                # Nudge the accept() loop
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.connect(self.socket_path)
                    s.close()
                except Exception:
                    pass
                break

    def _handle_signal(self, signum: int, frame: FrameType | None) -> None:
        del signum, frame
        self._running = False

    def _shutdown(self) -> None:
        self.manager.close()
        if self._ephemeral_dir is not None:
            shutil.rmtree(self._ephemeral_dir, ignore_errors=True)
        if self._server_socket:
            with contextlib.suppress(Exception):
                self._server_socket.close()
        self._cleanup_files()

    def _cleanup_stale(self) -> None:
        """Remove stale socket file if no daemon is running."""
        if os.path.exists(self.socket_path):
            # Check if another daemon is using it
            if os.path.exists(self.pid_path):
                alive = False
                pid = None
                try:
                    with open(self.pid_path) as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 0)
                    alive = True  # process exists and we can signal it
                except PermissionError:
                    alive = True  # process exists, owned by another user (EPERM)
                except (ProcessLookupError, ValueError):
                    pass  # stale pid or corrupt pid file, clean up
                if alive:
                    print(
                        f"[camoufox-cli] Daemon already running (pid {pid})",
                        file=sys.stderr,
                    )
                    sys.exit(1)
            os.unlink(self.socket_path)

    def _write_pid(self) -> None:
        with open(self.pid_path, "w") as f:
            _ = f.write(str(os.getpid()))

    def _cleanup_files(self) -> None:
        for path in (self.socket_path, self.pid_path):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)
