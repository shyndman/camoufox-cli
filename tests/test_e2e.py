"""End-to-end tests exercising daemon server + socket protocol + real browser."""

import contextlib
import json
import os
import signal
import socket
import threading
import time
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from camoufox_cli.models import OkResponse, Response, ResponseData, response_adapter
from camoufox_cli.server import DaemonServer

FIXTURE_URL = "file://" + os.path.join(os.path.dirname(__file__), "fixture.html")
TEST_SESSION = f"e2e-test-{os.getpid()}-{int(time.time())}"
SOCK_PATH = f"/tmp/camoufox-cli-{TEST_SESSION}.sock"
PID_PATH = f"/tmp/camoufox-cli-{TEST_SESSION}.pid"


def send_command(sock_path: str, cmd: dict[str, object]) -> Response:
    """Send a JSON command over Unix socket and return the parsed response."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall((json.dumps(cmd) + "\n").encode())
    data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
        if b"\n" in data:
            break
    s.close()
    return response_adapter.validate_json(data.decode().strip())


def wait_for_socket(path: str, timeout: float = 10.0) -> None:
    """Wait until socket file appears."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path):
            return
        time.sleep(0.1)
    raise TimeoutError(f"Socket {path} not found after {timeout}s")


def _start_daemon_thread(server: DaemonServer) -> None:
    """Start DaemonServer in a thread, skipping signal handlers (main-thread only)."""
    with patch.object(signal, "signal"):
        server.start()


@pytest.fixture(scope="module")
def daemon() -> Iterator[str]:
    """Start a DaemonServer in a background thread for all e2e tests."""
    server = DaemonServer(session=TEST_SESSION, headless=True, timeout=300)
    thread = threading.Thread(target=_start_daemon_thread, args=(server,), daemon=True)
    thread.start()
    wait_for_socket(SOCK_PATH)

    # Open fixture page
    resp = send_command(
        SOCK_PATH,
        {
            "id": "setup",
            "action": "open",
            "params": {"url": FIXTURE_URL},
        },
    )
    assert resp.success is True

    yield SOCK_PATH

    # Shut down daemon
    with contextlib.suppress(Exception):
        _ = send_command(SOCK_PATH, {"id": "teardown", "action": "close", "params": {}})
    thread.join(timeout=10)


def cmd(
    sock_path: str, action: str, params: dict[str, object] | None = None, id: str = "r1"
) -> Response:
    """Shorthand for send_command."""
    return send_command(sock_path, {"id": id, "action": action, "params": params or {}})


def ok(resp: Response) -> OkResponse:
    """Assert the response succeeded and return it narrowed to OkResponse."""
    assert isinstance(resp, OkResponse)
    return resp


def data(resp: Response) -> ResponseData:
    """Assert the response succeeded with a data payload and return it."""
    okresp = ok(resp)
    assert okresp.data is not None
    return okresp.data


def find_ref(snapshot_text: str, role: str) -> str:
    """Extract first ref for a given role from snapshot text."""
    for line in snapshot_text.split("\n"):
        if f"- {role}" in line and "[ref=" in line:
            start = line.index("[ref=") + 5
            end = line.index("]", start)
            return "@" + line[start:end]
    raise ValueError(f"No ref found for role '{role}' in snapshot")


def _snapshot_ref(sock_path: str, role: str) -> str:
    """Snapshot and extract the first ref for ``role``."""
    snapshot = data(cmd(sock_path, "snapshot")).snapshot
    assert snapshot is not None
    return find_ref(snapshot, role)


@pytest.mark.integration
class TestE2E:
    """E2E tests: daemon server + Unix socket + real browser."""

    def test_open_returns_url_and_title(self, daemon: str):
        url = data(cmd(daemon, "url")).url
        assert url is not None
        assert "fixture.html" in url

        assert data(cmd(daemon, "title")).title == "Test Fixture"

    def test_snapshot_has_refs(self, daemon: str):
        snapshot = data(cmd(daemon, "snapshot")).snapshot
        assert snapshot is not None
        assert "[ref=" in snapshot

    def test_fill_textbox(self, daemon: str):
        ref = _snapshot_ref(daemon, "textbox")

        assert ok(cmd(daemon, "fill", {"ref": ref, "text": "E2E-Alice"})).success

        resp = data(
            cmd(daemon, "eval", {"expression": "document.getElementById('name').value"})
        )
        assert resp.result == "E2E-Alice"

    def test_click_button(self, daemon: str):
        ref = _snapshot_ref(daemon, "button")

        assert ok(cmd(daemon, "click", {"ref": ref})).success

        resp = data(
            cmd(
                daemon,
                "eval",
                {"expression": "document.getElementById('output').textContent"},
            )
        )
        assert resp.result == "clicked"

    def test_click_js_anchor_fires_handler(self, daemon: str):
        # Regression for #2: clicking a JS-driven <a href="#"> must fire its
        # onclick handler instead of navigating via goto and skipping it.
        js_page = (
            "data:text/html,"
            "<a id='lnk' href='%23' onclick=\""
            "document.getElementById('out').textContent='clicked'\">go</a>"
            "<p id='out'>ready</p>"
        )
        assert ok(cmd(daemon, "open", {"url": js_page})).success

        ref = _snapshot_ref(daemon, "link")
        assert ok(cmd(daemon, "click", {"ref": ref})).success

        resp = data(
            cmd(
                daemon,
                "eval",
                {"expression": "document.getElementById('out').textContent"},
            )
        )
        assert resp.result == "clicked"

        # Restore fixture for subsequent tests.
        _ = cmd(daemon, "open", {"url": FIXTURE_URL})

    def test_select_dropdown(self, daemon: str):
        ref = _snapshot_ref(daemon, "combobox")

        assert ok(cmd(daemon, "select", {"ref": ref, "value": "Green"})).success

        resp = data(
            cmd(
                daemon, "eval", {"expression": "document.getElementById('color').value"}
            )
        )
        assert resp.result == "green"

    def test_check_uncheck(self, daemon: str):
        ref = _snapshot_ref(daemon, "checkbox")

        # Check
        assert ok(cmd(daemon, "check", {"ref": ref})).success
        resp = data(
            cmd(
                daemon,
                "eval",
                {"expression": "document.getElementById('agree').checked"},
            )
        )
        assert resp.result is True

        # Uncheck
        assert ok(cmd(daemon, "check", {"ref": ref})).success
        resp = data(
            cmd(
                daemon,
                "eval",
                {"expression": "document.getElementById('agree').checked"},
            )
        )
        assert resp.result is False

    def test_scroll(self, daemon: str):
        assert ok(cmd(daemon, "scroll", {"direction": "down", "amount": 100})).success

    def test_wait_ms(self, daemon: str):
        assert ok(cmd(daemon, "wait", {"ms": 50})).success

    def test_press_key(self, daemon: str):
        # Take snapshot and focus textbox first
        ref = _snapshot_ref(daemon, "textbox")
        _ = cmd(daemon, "click", {"ref": ref})

        assert ok(cmd(daemon, "press", {"key": "Tab"})).success

    def test_back_forward(self, daemon: str):
        # Navigate to a second page (use data: URI since about:blank may fail)
        assert ok(cmd(daemon, "open", {"url": "data:text/html,<h1>Page2</h1>"})).success

        # Go back to fixture
        url = data(cmd(daemon, "back")).url
        assert url is not None
        assert "fixture.html" in url

        # Go forward
        assert ok(cmd(daemon, "forward")).success

        # Navigate back to fixture for subsequent tests
        _ = cmd(daemon, "open", {"url": FIXTURE_URL})

    def test_tabs(self, daemon: str):
        tabs = data(cmd(daemon, "tabs")).tabs
        assert tabs is not None
        assert len(tabs) >= 1
        assert any(t["active"] for t in tabs)

    def test_cookies(self, daemon: str):
        assert data(cmd(daemon, "cookies", {"op": "list"})).cookies is not None

    def test_close_shuts_down_daemon(self):
        """Close command shuts down the daemon (run last, standalone)."""
        session = f"e2e-close-{os.getpid()}-{int(time.time())}"
        sock = f"/tmp/camoufox-cli-{session}.sock"
        server = DaemonServer(session=session, headless=True, timeout=60)
        thread = threading.Thread(
            target=_start_daemon_thread, args=(server,), daemon=True
        )
        thread.start()
        wait_for_socket(sock)

        resp = send_command(sock, {"id": "r1", "action": "close", "params": {}})
        assert resp.success is True

        thread.join(timeout=10)
        assert not os.path.exists(sock)
