"""Tests for CLI argument parsing and command building."""

import pytest

from camoufox_cli.cli import (
    build_command,
    parse_args,
    list_sessions,
    get_log_path,
    get_socket_path,
    _format_tabs,
    print_response,
)


class TestBuildCommand:
    # --- Navigation ---
    def test_open(self):
        cmd = build_command("open", ["open", "https://example.com"])
        assert cmd["action"] == "open"
        assert cmd["params"]["url"] == "https://example.com"

    def test_back(self):
        cmd = build_command("back", ["back"])
        assert cmd["action"] == "back"

    def test_forward(self):
        cmd = build_command("forward", ["forward"])
        assert cmd["action"] == "forward"

    def test_reload(self):
        cmd = build_command("reload", ["reload"])
        assert cmd["action"] == "reload"

    def test_url(self):
        cmd = build_command("url", ["url"])
        assert cmd["action"] == "url"

    def test_title(self):
        cmd = build_command("title", ["title"])
        assert cmd["action"] == "title"

    def test_close(self):
        cmd = build_command("close", ["close"])
        assert cmd["action"] == "close"

    def test_close_all(self):
        cmd = build_command("close", ["close", "--all"])
        assert cmd["params"]["all"] is True

    # --- Snapshot ---
    def test_snapshot_basic(self):
        cmd = build_command("snapshot", ["snapshot"])
        assert cmd["action"] == "snapshot"
        assert cmd["params"]["interactive"] is False

    def test_snapshot_interactive(self):
        cmd = build_command("snapshot", ["snapshot", "-i"])
        assert cmd["params"]["interactive"] is True

    def test_snapshot_scoped(self):
        cmd = build_command("snapshot", ["snapshot", "-s", "#main"])
        assert cmd["params"]["selector"] == "#main"

    # --- Interaction ---
    def test_click(self):
        cmd = build_command("click", ["click", "@e1"])
        assert cmd["action"] == "click"
        assert cmd["params"]["ref"] == "@e1"

    def test_fill(self):
        cmd = build_command("fill", ["fill", "@e1", "hello"])
        assert cmd["params"]["ref"] == "@e1"
        assert cmd["params"]["text"] == "hello"

    def test_type(self):
        cmd = build_command("type", ["type", "@e1", "hello"])
        assert cmd["params"]["ref"] == "@e1"
        assert cmd["params"]["text"] == "hello"

    def test_select(self):
        cmd = build_command("select", ["select", "@e1", "Option A"])
        assert cmd["params"]["ref"] == "@e1"
        assert cmd["params"]["value"] == "Option A"

    def test_check(self):
        cmd = build_command("check", ["check", "@e1"])
        assert cmd["params"]["ref"] == "@e1"

    def test_hover(self):
        cmd = build_command("hover", ["hover", "@e1"])
        assert cmd["params"]["ref"] == "@e1"

    def test_press(self):
        cmd = build_command("press", ["press", "Enter"])
        assert cmd["params"]["key"] == "Enter"

    # --- Data extraction ---
    def test_text(self):
        cmd = build_command("text", ["text", "@e1"])
        assert cmd["params"]["target"] == "@e1"

    def test_eval(self):
        cmd = build_command("eval", ["eval", "document.title"])
        assert cmd["params"]["expression"] == "document.title"

    def test_screenshot(self):
        cmd = build_command("screenshot", ["screenshot", "out.png"])
        assert cmd["params"]["path"] == "out.png"

    def test_screenshot_full(self):
        cmd = build_command("screenshot", ["screenshot", "--full", "out.png"])
        assert cmd["params"]["full_page"] is True
        assert cmd["params"]["path"] == "out.png"

    def test_screenshot_no_args(self):
        cmd = build_command("screenshot", ["screenshot"])
        assert "path" not in cmd["params"]

    # --- Scroll & Wait ---
    def test_scroll_down(self):
        cmd = build_command("scroll", ["scroll", "down"])
        assert cmd["params"]["direction"] == "down"
        assert cmd["params"]["amount"] == 500

    def test_scroll_up_custom(self):
        cmd = build_command("scroll", ["scroll", "up", "300"])
        assert cmd["params"]["direction"] == "up"
        assert cmd["params"]["amount"] == 300

    def test_wait_ms(self):
        cmd = build_command("wait", ["wait", "2000"])
        assert cmd["params"]["ms"] == 2000

    def test_wait_ref(self):
        cmd = build_command("wait", ["wait", "@e1"])
        assert cmd["params"]["ref"] == "@e1"

    def test_wait_selector(self):
        cmd = build_command("wait", ["wait", "#loading"])
        assert cmd["params"]["selector"] == "#loading"

    def test_wait_url(self):
        cmd = build_command("wait", ["wait", "--url", "*/dashboard"])
        assert cmd["params"]["url"] == "*/dashboard"

    # --- Tabs ---
    def test_tabs(self):
        cmd = build_command("tabs", ["tabs"])
        assert cmd["action"] == "tabs"

    def test_switch(self):
        cmd = build_command("switch", ["switch", "2"])
        assert cmd["params"]["index"] == 2

    def test_close_tab(self):
        cmd = build_command("close-tab", ["close-tab"])
        assert cmd["action"] == "close-tab"

    # --- Cookies ---
    def test_cookies_list(self):
        cmd = build_command("cookies", ["cookies"])
        assert cmd["params"]["op"] == "list"

    def test_cookies_export(self):
        cmd = build_command("cookies", ["cookies", "export", "c.json"])
        assert cmd["params"]["op"] == "export"
        assert cmd["params"]["path"] == "c.json"

    def test_cookies_import(self):
        cmd = build_command("cookies", ["cookies", "import", "c.json"])
        assert cmd["params"]["op"] == "import"
        assert cmd["params"]["path"] == "c.json"

    # --- Error cases ---
    def test_unknown_command(self):
        with pytest.raises(SystemExit):
            build_command("nonexistent", ["nonexistent"])

    def test_open_missing_url(self):
        with pytest.raises(SystemExit):
            build_command("open", ["open"])

    def test_click_missing_ref(self):
        with pytest.raises(SystemExit):
            build_command("click", ["click"])

    def test_fill_missing_text(self):
        with pytest.raises(SystemExit):
            build_command("fill", ["fill", "@e1"])

    # --- Numeric argument validation ---
    def test_scroll_non_integer(self):
        with pytest.raises(SystemExit):
            build_command("scroll", ["scroll", "down", "fast"])

    def test_scroll_below_minimum(self):
        with pytest.raises(SystemExit):
            build_command("scroll", ["scroll", "down", "0"])

    def test_wait_ms_non_integer(self):
        # Leading digit routes to ms parsing; trailing garbage must be rejected.
        with pytest.raises(SystemExit):
            build_command("wait", ["wait", "2000ms"])

    def test_switch_non_integer(self):
        with pytest.raises(SystemExit):
            build_command("switch", ["switch", "last"])

    def test_switch_negative_passes_through(self):
        # No client-side range check; the daemon owns the valid tab range.
        cmd = build_command("switch", ["switch", "-1"])
        assert cmd["params"]["index"] == -1


class TestParseArgs:
    def test_defaults(self):
        flags, cmd = parse_args(["open", "https://example.com"])
        assert flags["session"] == "default"
        assert flags["headed"] is False
        assert flags["timeout"] == 1800
        assert flags["json"] is False
        assert flags["persistent"] is None
        assert flags["proxy"] is None
        assert flags["geoip"] is True

    def test_session_flag(self):
        flags, cmd = parse_args(["--session", "mysession", "open", "https://example.com"])
        assert flags["session"] == "mysession"

    def test_headed_flag(self):
        flags, cmd = parse_args(["--headed", "open", "https://example.com"])
        assert flags["headed"] is True

    def test_timeout_flag(self):
        flags, cmd = parse_args(["--timeout", "60", "open", "https://example.com"])
        assert flags["timeout"] == 60

    def test_json_flag(self):
        flags, cmd = parse_args(["--json", "open", "https://example.com"])
        assert flags["json"] is True

    def test_persistent_flag(self):
        flags, cmd = parse_args(["--persistent", "/tmp/profile", "open", "https://example.com"])
        assert flags["persistent"] == "/tmp/profile"

    def test_proxy_flag(self):
        flags, cmd = parse_args(["--proxy", "http://127.0.0.1:8080", "open", "https://example.com"])
        assert flags["proxy"] == "http://127.0.0.1:8080"

    def test_proxy_flag_with_auth(self):
        flags, cmd = parse_args(["--proxy", "http://user:pass@host:8080", "open", "https://example.com"])
        assert flags["proxy"] == "http://user:pass@host:8080"

    def test_missing_proxy_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--proxy"])

    def test_no_geoip_flag(self):
        flags, cmd = parse_args(["--no-geoip", "open", "https://example.com"])
        assert flags["geoip"] is False

    def test_multiple_flags(self):
        flags, cmd = parse_args(["--headed", "--json", "--session", "s1", "snapshot", "-i"])
        assert flags["headed"] is True
        assert flags["json"] is True
        assert flags["session"] == "s1"
        assert cmd["params"]["interactive"] is True

    def test_no_command(self):
        with pytest.raises(SystemExit):
            parse_args([])

    def test_missing_session_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--session"])

    def test_missing_timeout_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--timeout"])

    def test_timeout_non_integer(self):
        with pytest.raises(SystemExit):
            parse_args(["--timeout", "soon", "open", "https://example.com"])

    def test_timeout_below_minimum(self):
        with pytest.raises(SystemExit):
            parse_args(["--timeout", "0", "open", "https://example.com"])


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
        tabs = [
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
        tabs = [
            {"index": 0, "url": "https://a", "title": "short", "active": True},
            {"index": 1, "url": "https://b", "title": "a much longer title", "active": False},
        ]
        lines = _format_tabs(tabs).splitlines()
        assert lines[0].index("https://a") == lines[1].index("https://b")


class TestPrintResponseTabs:
    def test_renders_table_for_tabs_only_response(self, capsys):
        resp = {
            "success": True,
            "data": {"tabs": [{"index": 0, "url": "https://a", "title": "A", "active": True}]},
        }
        print_response(resp, json_mode=False)
        out = capsys.readouterr().out
        assert "* 0" in out
        assert "{" not in out  # not a raw JSON dump

    def test_appends_table_after_primary_output(self, capsys):
        resp = {
            "success": True,
            "data": {
                "text": "hello",
                "tabs": [{"index": 0, "url": "https://a", "title": "A", "active": True}],
            },
        }
        print_response(resp, json_mode=False)
        lines = capsys.readouterr().out.splitlines()
        assert lines[0] == "hello"
        assert lines[1].startswith("* 0")
