"""Tests for CLI argument parsing and command building."""

import json
import os
import socket
import tempfile
import threading
import time

import pytest

from camoufox_cli.cli import (
    ResponseError,
    _format_tabs,
    build_command,
    get_log_path,
    get_socket_path,
    parse_args,
    print_response,
    send_command,
)
from camoufox_cli.models import (
    BackCommand,
    CheckCommand,
    ClickCommand,
    CloseCommand,
    CloseTabCommand,
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
from camoufox_cli.types import Tab


class TestBuildCommand:
    # --- Navigation ---
    def test_open(self):
        cmd = build_command("open", ["open", "https://example.com"])
        assert isinstance(cmd, OpenCommand)
        assert cmd.params.url == "https://example.com"

    def test_back(self):
        cmd = build_command("back", ["back"])
        assert isinstance(cmd, BackCommand)

    def test_forward(self):
        cmd = build_command("forward", ["forward"])
        assert isinstance(cmd, ForwardCommand)

    def test_reload(self):
        cmd = build_command("reload", ["reload"])
        assert isinstance(cmd, ReloadCommand)

    def test_url(self):
        cmd = build_command("url", ["url"])
        assert isinstance(cmd, UrlCommand)

    def test_title(self):
        cmd = build_command("title", ["title"])
        assert isinstance(cmd, TitleCommand)

    def test_close(self):
        cmd = build_command("close", ["close"])
        assert isinstance(cmd, CloseCommand)

    def test_close_all(self):
        cmd = build_command("close", ["close", "--all"])
        assert isinstance(cmd, CloseCommand)
        assert cmd.params.all is True

    # --- Snapshot ---
    def test_snapshot_basic(self):
        cmd = build_command("snapshot", ["snapshot"])
        assert isinstance(cmd, SnapshotCommand)
        assert cmd.params.interactive is False

    def test_snapshot_interactive(self):
        cmd = build_command("snapshot", ["snapshot", "-i"])
        assert isinstance(cmd, SnapshotCommand)
        assert cmd.params.interactive is True

    def test_snapshot_scoped(self):
        cmd = build_command("snapshot", ["snapshot", "-s", "#main"])
        assert isinstance(cmd, SnapshotCommand)
        assert cmd.params.selector == "#main"

    # --- Interaction ---
    def test_click(self):
        cmd = build_command("click", ["click", "@e1"])
        assert isinstance(cmd, ClickCommand)
        assert cmd.params.ref == "@e1"

    def test_fill(self):
        cmd = build_command("fill", ["fill", "@e1", "hello"])
        assert isinstance(cmd, FillCommand)
        assert cmd.params.ref == "@e1"
        assert cmd.params.text == "hello"

    def test_type(self):
        cmd = build_command("type", ["type", "@e1", "hello"])
        assert isinstance(cmd, TypeCommand)
        assert cmd.params.ref == "@e1"
        assert cmd.params.text == "hello"

    def test_select(self):
        cmd = build_command("select", ["select", "@e1", "Option A"])
        assert isinstance(cmd, SelectCommand)
        assert cmd.params.ref == "@e1"
        assert cmd.params.value == "Option A"

    def test_check(self):
        cmd = build_command("check", ["check", "@e1"])
        assert isinstance(cmd, CheckCommand)
        assert cmd.params.ref == "@e1"

    def test_hover(self):
        cmd = build_command("hover", ["hover", "@e1"])
        assert isinstance(cmd, HoverCommand)
        assert cmd.params.ref == "@e1"

    def test_press(self):
        cmd = build_command("press", ["press", "Enter"])
        assert isinstance(cmd, PressCommand)
        assert cmd.params.key == "Enter"

    # --- Data extraction ---
    def test_text(self):
        cmd = build_command("text", ["text", "@e1"])
        assert isinstance(cmd, TextCommand)
        assert cmd.params.target == "@e1"

    def test_eval(self):
        cmd = build_command("eval", ["eval", "document.title"])
        assert isinstance(cmd, EvalCommand)
        assert cmd.params.expression == "document.title"

    def test_screenshot(self):
        cmd = build_command("screenshot", ["screenshot", "out.png"])
        assert isinstance(cmd, ScreenshotCommand)
        assert cmd.params.path == "out.png"

    def test_screenshot_full(self):
        cmd = build_command("screenshot", ["screenshot", "--full", "out.png"])
        assert isinstance(cmd, ScreenshotCommand)
        assert cmd.params.full_page is True
        assert cmd.params.path == "out.png"

    def test_screenshot_no_args(self):
        cmd = build_command("screenshot", ["screenshot"])
        assert isinstance(cmd, ScreenshotCommand)
        assert cmd.params.path is None

    # --- Scroll & Wait ---
    def test_scroll_down(self):
        cmd = build_command("scroll", ["scroll", "down"])
        assert isinstance(cmd, ScrollCommand)
        assert cmd.params.direction == "down"
        assert cmd.params.amount == 500

    def test_scroll_up_custom(self):
        cmd = build_command("scroll", ["scroll", "up", "300"])
        assert isinstance(cmd, ScrollCommand)
        assert cmd.params.direction == "up"
        assert cmd.params.amount == 300

    def test_wait_ms(self):
        cmd = build_command("wait", ["wait", "2000"])
        assert isinstance(cmd, WaitCommand)
        assert cmd.params.ms == 2000

    def test_wait_ref(self):
        cmd = build_command("wait", ["wait", "@e1"])
        assert isinstance(cmd, WaitCommand)
        assert cmd.params.ref == "@e1"

    def test_wait_selector(self):
        cmd = build_command("wait", ["wait", "#loading"])
        assert isinstance(cmd, WaitCommand)
        assert cmd.params.selector == "#loading"

    def test_wait_url(self):
        cmd = build_command("wait", ["wait", "--url", "*/dashboard"])
        assert isinstance(cmd, WaitCommand)
        assert cmd.params.url == "*/dashboard"

    # --- Tabs ---
    def test_tabs(self):
        cmd = build_command("tabs", ["tabs"])
        assert isinstance(cmd, TabsCommand)

    def test_switch(self):
        cmd = build_command("switch", ["switch", "2"])
        assert isinstance(cmd, SwitchCommand)
        assert cmd.params.index == 2

    def test_close_tab(self):
        cmd = build_command("close-tab", ["close-tab"])
        assert isinstance(cmd, CloseTabCommand)

    # --- Cookies ---
    def test_cookies_list(self):
        cmd = build_command("cookies", ["cookies"])
        assert isinstance(cmd, CookiesCommand)
        assert cmd.params.op == "list"

    def test_cookies_export(self):
        cmd = build_command("cookies", ["cookies", "export", "c.json"])
        assert isinstance(cmd, CookiesCommand)
        assert cmd.params.op == "export"
        assert cmd.params.path == "c.json"

    def test_cookies_import(self):
        cmd = build_command("cookies", ["cookies", "import", "c.json"])
        assert isinstance(cmd, CookiesCommand)
        assert cmd.params.op == "import"
        assert cmd.params.path == "c.json"

    # --- Error cases ---
    def test_unknown_command(self):
        with pytest.raises(SystemExit):
            _ = build_command("nonexistent", ["nonexistent"])

    def test_open_missing_url(self):
        with pytest.raises(SystemExit):
            _ = build_command("open", ["open"])

    def test_click_missing_ref(self):
        with pytest.raises(SystemExit):
            _ = build_command("click", ["click"])

    def test_fill_missing_text(self):
        with pytest.raises(SystemExit):
            _ = build_command("fill", ["fill", "@e1"])

    # --- Numeric argument validation ---
    def test_scroll_non_integer(self):
        with pytest.raises(SystemExit):
            _ = build_command("scroll", ["scroll", "down", "fast"])

    def test_scroll_below_minimum(self):
        with pytest.raises(SystemExit):
            _ = build_command("scroll", ["scroll", "down", "0"])

    def test_wait_ms_non_integer(self):
        # Leading digit routes to ms parsing; trailing garbage must be rejected.
        with pytest.raises(SystemExit):
            _ = build_command("wait", ["wait", "2000ms"])

    def test_switch_non_integer(self):
        with pytest.raises(SystemExit):
            _ = build_command("switch", ["switch", "last"])

    def test_switch_negative_passes_through(self):
        # No client-side range check; the daemon owns the valid tab range.
        cmd = build_command("switch", ["switch", "-1"])
        assert isinstance(cmd, SwitchCommand)
        assert cmd.params.index == -1


class TestParseArgs:
    def test_defaults(self):
        flags, _ = parse_args(["open", "https://example.com"])
        assert flags.session == "default"
        assert flags.headed is False
        assert flags.timeout == 1800
        assert flags.json is False
        assert flags.persistent is None
        assert flags.proxy is None
        assert flags.geoip is True

    def test_session_flag(self):
        flags, _ = parse_args(["--session", "mysession", "open", "https://example.com"])
        assert flags.session == "mysession"

    def test_headed_flag(self):
        flags, _ = parse_args(["--headed", "open", "https://example.com"])
        assert flags.headed is True

    def test_timeout_flag(self):
        flags, _ = parse_args(["--timeout", "60", "open", "https://example.com"])
        assert flags.timeout == 60

    def test_json_flag(self):
        flags, _ = parse_args(["--json", "open", "https://example.com"])
        assert flags.json is True

    def test_persistent_flag(self):
        flags, _ = parse_args(
            ["--persistent", "/tmp/profile", "open", "https://example.com"]
        )
        assert flags.persistent == "/tmp/profile"

    def test_proxy_flag(self):
        flags, _ = parse_args(
            ["--proxy", "http://127.0.0.1:8080", "open", "https://example.com"]
        )
        assert flags.proxy == "http://127.0.0.1:8080"

    def test_proxy_flag_with_auth(self):
        flags, _ = parse_args(
            ["--proxy", "http://user:pass@host:8080", "open", "https://example.com"]
        )
        assert flags.proxy == "http://user:pass@host:8080"

    def test_missing_proxy_value(self):
        with pytest.raises(SystemExit):
            _ = parse_args(["--proxy"])

    def test_no_geoip_flag(self):
        flags, _ = parse_args(["--no-geoip", "open", "https://example.com"])
        assert flags.geoip is False

    def test_multiple_flags(self):
        flags, cmd = parse_args(
            ["--headed", "--json", "--session", "s1", "snapshot", "-i"]
        )
        assert flags.headed is True
        assert flags.json is True
        assert flags.session == "s1"
        assert isinstance(cmd, SnapshotCommand)
        assert cmd.params.interactive is True

    def test_no_command(self):
        with pytest.raises(SystemExit):
            _ = parse_args([])

    def test_missing_session_value(self):
        with pytest.raises(SystemExit):
            _ = parse_args(["--session"])

    def test_missing_timeout_value(self):
        with pytest.raises(SystemExit):
            _ = parse_args(["--timeout"])

    def test_timeout_non_integer(self):
        with pytest.raises(SystemExit):
            _ = parse_args(["--timeout", "soon", "open", "https://example.com"])

    def test_timeout_below_minimum(self):
        with pytest.raises(SystemExit):
            _ = parse_args(["--timeout", "0", "open", "https://example.com"])


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
