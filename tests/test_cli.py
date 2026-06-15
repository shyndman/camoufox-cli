"""Tests for the Typer CLI app, output formatting, and transport safety."""

import json
import os
import socket
import tempfile
import threading
import time

import pytest
from typer.testing import CliRunner

from camoufox_cli import operations as ops
from camoufox_cli.cli import _format_tabs, app, print_response
from camoufox_cli.models import (
    BackCommand,
    CheckCommand,
    ClickCommand,
    CloseCommand,
    CloseTabCommand,
    Command,
    CookiesCommand,
    EvalCommand,
    FillCommand,
    ForwardCommand,
    HoverCommand,
    OkResponse,
    OpenCommand,
    PressCommand,
    ReloadCommand,
    ResponseData,
    ScreenshotCommand,
    ScrollCommand,
    ScrollDirection,
    SelectCommand,
    SnapshotCommand,
    SwitchCommand,
    TabsCommand,
    TextCommand,
    TitleCommand,
    TypeCommand,
    UrlCommand,
    WaitCommand,
)
from camoufox_cli.operations import (
    ResponseError,
    get_log_path,
    get_socket_path,
    send_command,
)
from camoufox_cli.types import Tab

runner = CliRunner()


@pytest.fixture
def cap(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Intercept the daemon transport so commands are captured, not sent.

    ``box["flags"]`` is the positional tuple passed to ``ensure_daemon`` and
    ``box["command"]`` is the typed command that ``_run`` would transmit.
    """
    box: dict[str, object] = {}

    def fake_ensure(
        session: str,
        headed: bool,
        timeout: int,
        persistent: str | None,
        proxy: str | None,
        geoip: bool,
        locale: str | None,
    ) -> None:
        box["flags"] = (session, headed, timeout, persistent, proxy, geoip, locale)

    def fake_send(_sock_path: str, command: Command) -> OkResponse:
        box["command"] = command
        return OkResponse(id="r1")

    monkeypatch.setattr(ops, "ensure_daemon", fake_ensure)
    monkeypatch.setattr(ops, "send_command", fake_send)
    return box


class TestCli:
    """Drive the Typer app end-to-end (transport monkeypatched via ``cap``)."""

    # --- Navigation ---
    def test_open(self, cap: dict[str, object]):
        result = runner.invoke(app, ["open", "https://example.com"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, OpenCommand)
        assert cmd.params.url == "https://example.com"

    def test_back(self, cap: dict[str, object]):
        result = runner.invoke(app, ["back"])
        assert result.exit_code == 0
        assert isinstance(cap["command"], BackCommand)

    def test_forward(self, cap: dict[str, object]):
        result = runner.invoke(app, ["forward"])
        assert result.exit_code == 0
        assert isinstance(cap["command"], ForwardCommand)

    def test_reload(self, cap: dict[str, object]):
        result = runner.invoke(app, ["reload"])
        assert result.exit_code == 0
        assert isinstance(cap["command"], ReloadCommand)

    def test_url(self, cap: dict[str, object]):
        result = runner.invoke(app, ["url"])
        assert result.exit_code == 0
        assert isinstance(cap["command"], UrlCommand)

    def test_title(self, cap: dict[str, object]):
        result = runner.invoke(app, ["title"])
        assert result.exit_code == 0
        assert isinstance(cap["command"], TitleCommand)

    def test_close(self, cap: dict[str, object]):
        result = runner.invoke(app, ["close"])
        assert result.exit_code == 0
        assert isinstance(cap["command"], CloseCommand)

    # --- Snapshot ---
    def test_snapshot_basic(self, cap: dict[str, object]):
        result = runner.invoke(app, ["snapshot"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, SnapshotCommand)
        assert cmd.params.interactive is False

    def test_snapshot_interactive(self, cap: dict[str, object]):
        result = runner.invoke(app, ["snapshot", "-i"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, SnapshotCommand)
        assert cmd.params.interactive is True

    def test_snapshot_scoped(self, cap: dict[str, object]):
        result = runner.invoke(app, ["snapshot", "-s", "#main"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, SnapshotCommand)
        assert cmd.params.selector == "#main"

    # --- Interaction ---
    def test_click(self, cap: dict[str, object]):
        result = runner.invoke(app, ["click", "@e1"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, ClickCommand)
        assert cmd.params.ref == "@e1"

    def test_fill(self, cap: dict[str, object]):
        result = runner.invoke(app, ["fill", "@e1", "hello"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, FillCommand)
        assert cmd.params.ref == "@e1"
        assert cmd.params.text == "hello"

    def test_type(self, cap: dict[str, object]):
        result = runner.invoke(app, ["type", "@e1", "hello"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, TypeCommand)
        assert cmd.params.ref == "@e1"
        assert cmd.params.text == "hello"

    def test_select(self, cap: dict[str, object]):
        result = runner.invoke(app, ["select", "@e1", "Option A"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, SelectCommand)
        assert cmd.params.ref == "@e1"
        assert cmd.params.value == "Option A"

    def test_check(self, cap: dict[str, object]):
        result = runner.invoke(app, ["check", "@e1"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, CheckCommand)
        assert cmd.params.ref == "@e1"

    def test_hover(self, cap: dict[str, object]):
        result = runner.invoke(app, ["hover", "@e1"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, HoverCommand)
        assert cmd.params.ref == "@e1"

    def test_press(self, cap: dict[str, object]):
        result = runner.invoke(app, ["press", "Enter"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, PressCommand)
        assert cmd.params.key == "Enter"

    # --- Data extraction ---
    def test_text(self, cap: dict[str, object]):
        result = runner.invoke(app, ["text", "@e1"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, TextCommand)
        assert cmd.params.target == "@e1"

    def test_eval(self, cap: dict[str, object]):
        result = runner.invoke(app, ["eval", "document.title"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, EvalCommand)
        assert cmd.params.expression == "document.title"

    def test_screenshot(self, cap: dict[str, object]):
        result = runner.invoke(app, ["screenshot", "out.png"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, ScreenshotCommand)
        assert cmd.params.path == "out.png"

    def test_screenshot_full(self, cap: dict[str, object]):
        result = runner.invoke(app, ["screenshot", "--full", "out.png"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, ScreenshotCommand)
        assert cmd.params.full_page is True
        assert cmd.params.path == "out.png"

    def test_screenshot_no_args(self, cap: dict[str, object]):
        result = runner.invoke(app, ["screenshot"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, ScreenshotCommand)
        assert cmd.params.path is None

    # --- Scroll & Wait ---
    def test_scroll_down(self, cap: dict[str, object]):
        result = runner.invoke(app, ["scroll", "down"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, ScrollCommand)
        assert cmd.params.direction == ScrollDirection.down
        assert cmd.params.amount == 500

    def test_scroll_up_custom(self, cap: dict[str, object]):
        result = runner.invoke(app, ["scroll", "up", "300"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, ScrollCommand)
        assert cmd.params.direction == ScrollDirection.up
        assert cmd.params.amount == 300

    def test_scroll_left(self, cap: dict[str, object]):
        result = runner.invoke(app, ["scroll", "left"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, ScrollCommand)
        assert cmd.params.direction == ScrollDirection.left

    def test_scroll_right(self, cap: dict[str, object]):
        result = runner.invoke(app, ["scroll", "right", "800"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, ScrollCommand)
        assert cmd.params.direction == ScrollDirection.right
        assert cmd.params.amount == 800

    def test_wait_ms(self, cap: dict[str, object]):
        result = runner.invoke(app, ["wait", "2000"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, WaitCommand)
        assert cmd.params.ms == 2000

    def test_wait_ref(self, cap: dict[str, object]):
        result = runner.invoke(app, ["wait", "@e1"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, WaitCommand)
        assert cmd.params.ref == "@e1"

    def test_wait_selector(self, cap: dict[str, object]):
        result = runner.invoke(app, ["wait", "#loading"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, WaitCommand)
        assert cmd.params.selector == "#loading"

    def test_wait_url(self, cap: dict[str, object]):
        result = runner.invoke(app, ["wait", "--url", "*/dashboard"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, WaitCommand)
        assert cmd.params.url == "*/dashboard"

    # --- Tabs ---
    def test_tabs(self, cap: dict[str, object]):
        result = runner.invoke(app, ["tabs"])
        assert result.exit_code == 0
        assert isinstance(cap["command"], TabsCommand)

    def test_switch(self, cap: dict[str, object]):
        result = runner.invoke(app, ["switch", "2"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, SwitchCommand)
        assert cmd.params.index == 2

    def test_close_tab(self, cap: dict[str, object]):
        result = runner.invoke(app, ["close-tab"])
        assert result.exit_code == 0
        assert isinstance(cap["command"], CloseTabCommand)

    # --- Cookies sub-app ---
    def test_cookies_list(self, cap: dict[str, object]):
        result = runner.invoke(app, ["cookies", "list"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, CookiesCommand)
        assert cmd.params.op == "list"

    def test_cookies_export(self, cap: dict[str, object]):
        result = runner.invoke(app, ["cookies", "export", "c.json"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, CookiesCommand)
        assert cmd.params.op == "export"
        assert cmd.params.path == "c.json"

    def test_cookies_import(self, cap: dict[str, object]):
        result = runner.invoke(app, ["cookies", "import", "c.json"])
        assert result.exit_code == 0
        cmd = cap["command"]
        assert isinstance(cmd, CookiesCommand)
        assert cmd.params.op == "import"
        assert cmd.params.path == "c.json"

    # --- Error cases ---
    def test_unknown_command(self, cap: dict[str, object]):
        assert runner.invoke(app, ["nonexistent"]).exit_code != 0
        assert "command" not in cap

    def test_open_missing_url(self, cap: dict[str, object]):
        assert runner.invoke(app, ["open"]).exit_code != 0
        assert "command" not in cap

    def test_fill_missing_text(self, cap: dict[str, object]):
        assert runner.invoke(app, ["fill", "@e1"]).exit_code != 0
        assert "command" not in cap

    def test_scroll_non_integer(self, cap: dict[str, object]):
        assert runner.invoke(app, ["scroll", "down", "fast"]).exit_code != 0
        assert "command" not in cap

    def test_scroll_below_minimum(self, cap: dict[str, object]):
        assert runner.invoke(app, ["scroll", "down", "0"]).exit_code != 0
        assert "command" not in cap

    def test_scroll_bad_direction(self, cap: dict[str, object]):
        assert runner.invoke(app, ["scroll", "sideways", "100"]).exit_code != 0
        assert "command" not in cap

    def test_wait_ms_non_integer(self, cap: dict[str, object]):
        # Leading digit routes to ms parsing; trailing garbage must be rejected.
        assert runner.invoke(app, ["wait", "2000ms"]).exit_code != 0
        assert "command" not in cap

    def test_switch_non_integer(self, cap: dict[str, object]):
        assert runner.invoke(app, ["switch", "last"]).exit_code != 0
        assert "command" not in cap

    def test_timeout_non_integer(self, cap: dict[str, object]):
        result = runner.invoke(app, ["--timeout", "soon", "open", "https://x"])
        assert result.exit_code != 0
        assert "command" not in cap

    def test_timeout_below_minimum(self, cap: dict[str, object]):
        result = runner.invoke(app, ["--timeout", "0", "open", "https://x"])
        assert result.exit_code != 0
        assert "command" not in cap

    # --- Flag resolution ---
    def test_persistent_bare_resolves_default_path(self, cap: dict[str, object]):
        result = runner.invoke(app, ["--persistent", "open", "https://x"])
        assert result.exit_code == 0
        flags = cap["flags"]
        assert isinstance(flags, tuple)
        assert flags[3] == os.path.expanduser("~/.camoufox-cli/profiles/default")

    def test_user_data_dir_explicit_path(self, cap: dict[str, object]):
        result = runner.invoke(app, ["--user-data-dir", "/tmp/p", "open", "https://x"])
        assert result.exit_code == 0
        flags = cap["flags"]
        assert isinstance(flags, tuple)
        assert flags[3] == "/tmp/p"

    def test_no_persistence_is_none(self, cap: dict[str, object]):
        result = runner.invoke(app, ["open", "https://x"])
        assert result.exit_code == 0
        flags = cap["flags"]
        assert isinstance(flags, tuple)
        assert flags[3] is None

    def test_no_geoip(self, cap: dict[str, object]):
        result = runner.invoke(app, ["--no-geoip", "open", "https://x"])
        assert result.exit_code == 0
        flags = cap["flags"]
        assert isinstance(flags, tuple)
        assert flags[5] is False

    def test_session_flag(self, cap: dict[str, object]):
        result = runner.invoke(app, ["--session", "s1", "open", "https://x"])
        assert result.exit_code == 0
        flags = cap["flags"]
        assert isinstance(flags, tuple)
        assert flags[0] == "s1"

    # --- Flag ordering: global options must precede the subcommand ---
    def test_option_after_subcommand_rejected(self, cap: dict[str, object]):
        result = runner.invoke(app, ["open", "https://x", "--session", "s1"])
        assert result.exit_code != 0
        assert "command" not in cap


class TestGetSocketPath:
    def test_default_session(self):
        assert get_socket_path("default") == "/tmp/camoufox-cli-default.sock"

    def test_custom_session(self):
        assert get_socket_path("my-session") == "/tmp/camoufox-cli-my-session.sock"


class TestGetLogPath:
    def test_default_session(self):
        assert get_log_path("default") == "/tmp/camoufox-cli-default.log"

    def test_custom_session(self):
        assert get_log_path("my-session") == "/tmp/camoufox-cli-my-session.log"


class TestFormatTabs:
    def test_active_tab_is_marked(self):
        tabs: list[Tab] = [
            {"index": 0, "url": "https://a", "title": "A", "active": False},
            {"index": 1, "url": "https://b", "title": "B", "active": True},
        ]
        lines = _format_tabs(tabs).splitlines()
        assert lines[0][0] == " "
        assert lines[1].startswith("* 1")
        assert "0" in lines[0]
        assert "https://b" in lines[1]

    def test_empty_tab_list(self):
        assert _format_tabs([]) == "(no tabs)"

    def test_titles_are_column_aligned(self):
        tabs: list[Tab] = [
            {"index": 0, "url": "https://a", "title": "short", "active": True},
            {
                "index": 1,
                "url": "https://b",
                "title": "a much longer title",
                "active": False,
            },
        ]
        lines = _format_tabs(tabs).splitlines()
        assert lines[0].index("https://a") == lines[1].index("https://b")


class TestPrintResponseTabs:
    def test_renders_table_for_tabs_only_response(
        self, capsys: pytest.CaptureFixture[str]
    ):
        resp = OkResponse(
            id="r1",
            data=ResponseData(
                tabs=[{"index": 0, "url": "https://a", "title": "A", "active": True}]
            ),
        )
        print_response(resp, json_mode=False)
        out = capsys.readouterr().out
        assert "* 0" in out
        assert "{" not in out  # not a raw JSON dump

    def test_appends_table_after_primary_output(
        self, capsys: pytest.CaptureFixture[str]
    ):
        resp = OkResponse(
            id="r1",
            data=ResponseData(
                text="hello",
                tabs=[{"index": 0, "url": "https://a", "title": "A", "active": True}],
            ),
        )
        print_response(resp, json_mode=False)
        lines = capsys.readouterr().out.splitlines()
        assert lines[0] == "hello"
        assert lines[1].startswith("* 0")


class TestSendCommandRetrySafety:
    """Regression for issue #3: a reply failure after the command is delivered
    must surface as ResponseError so the caller never re-runs the action."""

    def _serve_once(
        self, sock_path: str, counter: list[int], reply: bytes
    ) -> threading.Thread:
        def run() -> None:
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(sock_path)
            srv.listen(1)
            srv.settimeout(5)
            conn: socket.socket
            # socket.accept() peer address is Any in typeshed; discarded _ stays Any.
            conn, _ = srv.accept()  # pyright: ignore[reportAny]
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            counter[0] += 1  # the (non-idempotent) action runs here
            conn.sendall(reply)
            conn.close()
            srv.close()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        return t

    def test_truncated_reply_raises_response_error_without_re_execution(self):
        d = tempfile.mkdtemp()
        sock_path = os.path.join(d, "d.sock")
        counter = [0]
        # Daemon dies mid-response: truncated JSON the client cannot parse.
        t = self._serve_once(sock_path, counter, b'{"id":"r1","succ')
        time.sleep(0.1)

        with pytest.raises(ResponseError):
            _ = send_command(sock_path, TitleCommand(id="r1"))

        t.join(timeout=5)
        assert counter[0] == 1  # executed exactly once; no internal retry

    def test_successful_reply_returns_parsed_response(self):
        d = tempfile.mkdtemp()
        sock_path = os.path.join(d, "d.sock")
        counter = [0]
        reply = json.dumps({"id": "r1", "success": True, "data": {}}).encode()
        t = self._serve_once(sock_path, counter, reply)
        time.sleep(0.1)

        resp = send_command(sock_path, TitleCommand(id="r1"))

        t.join(timeout=5)
        assert resp.success is True
        assert counter[0] == 1

    def test_connect_failure_is_not_response_error(self):
        # A daemon that is not yet up must remain retryable (not ResponseError).
        missing = os.path.join(tempfile.mkdtemp(), "nope.sock")
        with pytest.raises(Exception) as exc:
            _ = send_command(missing, TitleCommand(id="r1"))
        assert not isinstance(exc.value, ResponseError)
