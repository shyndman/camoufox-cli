import os

from types import SimpleNamespace

import pytest

from camoufox_cli import server
from camoufox_cli.server import DaemonServer


def _make_server(tmp_path):
    d = object.__new__(DaemonServer)
    d.socket_path = str(tmp_path / "camoufox.sock")
    d.pid_path = str(tmp_path / "camoufox.pid")
    open(d.socket_path, "w").close()
    with open(d.pid_path, "w") as f:
        f.write("424242")
    return d


class TestCleanupStale:
    def test_permission_error_preserves_live_socket(self, tmp_path, monkeypatch):
        d = _make_server(tmp_path)
        monkeypatch.setattr(server.os, "kill", _raise(PermissionError))
        with pytest.raises(SystemExit):
            d._cleanup_stale()
        assert os.path.exists(d.socket_path)

    def test_live_process_aborts_and_preserves_socket(self, tmp_path, monkeypatch):
        d = _make_server(tmp_path)
        monkeypatch.setattr(server.os, "kill", lambda pid, sig: None)
        with pytest.raises(SystemExit):
            d._cleanup_stale()
        assert os.path.exists(d.socket_path)

    def test_dead_process_removes_stale_socket(self, tmp_path, monkeypatch):
        d = _make_server(tmp_path)
        monkeypatch.setattr(server.os, "kill", _raise(ProcessLookupError))
        d._cleanup_stale()
        assert not os.path.exists(d.socket_path)

    def test_corrupt_pid_file_removes_stale_socket(self, tmp_path):
        d = _make_server(tmp_path)
        with open(d.pid_path, "w") as f:
            f.write("not-a-pid")
        d._cleanup_stale()
        assert not os.path.exists(d.socket_path)


def _raise(exc):
    def _kill(pid, sig):
        raise exc

    return _kill


class FakeManager:
    def __init__(self, pages, tabs, running=True):
        self._pages = pages
        self._tabs = tabs
        self._running = running

    @property
    def is_running(self):
        return self._running

    def get_context(self):
        if not self._running:
            raise RuntimeError("Browser not launched.")
        return SimpleNamespace(pages=self._pages)

    def get_tabs(self):
        return self._tabs


def _inject_server(manager):
    d = object.__new__(DaemonServer)
    d.manager = manager
    d._last_tab_sig = None
    return d


def _ok(data=None):
    resp = {"id": "r1", "success": True}
    if data is not None:
        resp["data"] = data
    return resp


class TestInjectTabChanges:
    def test_injects_tab_list_when_set_changes(self):
        pages = [object(), object()]
        tabs = [{"index": 0, "active": True}, {"index": 1, "active": False}]
        d = _inject_server(FakeManager(pages, tabs))

        resp = _ok()
        d._inject_tab_changes(resp)

        assert resp["data"]["tabs"] == tabs

    def test_does_not_reinject_when_set_unchanged(self):
        pages = [object(), object()]
        d = _inject_server(FakeManager(pages, [{"index": 0, "active": True}]))

        first = _ok()
        d._inject_tab_changes(first)
        assert "tabs" in first["data"]

        second = _ok()
        d._inject_tab_changes(second)
        assert "data" not in second or "tabs" not in second.get("data", {})

    def test_skips_when_browser_not_running(self):
        d = _inject_server(FakeManager([], [], running=False))

        resp = _ok()
        d._inject_tab_changes(resp)

        assert "data" not in resp or "tabs" not in resp.get("data", {})

    def test_skips_on_failed_response(self):
        pages = [object()]
        d = _inject_server(FakeManager(pages, [{"index": 0, "active": True}]))

        resp = {"id": "r1", "success": False, "error": "boom"}
        d._inject_tab_changes(resp)

        assert "data" not in resp

    def test_does_not_overwrite_handler_tab_list(self):
        """A tab command already carries its own list; injection must not clobber it."""
        pages = [object()]
        handler_tabs = [{"index": 0, "active": True, "url": "https://handler"}]
        d = _inject_server(FakeManager(pages, [{"index": 0, "active": False}]))

        resp = _ok({"tabs": handler_tabs})
        d._inject_tab_changes(resp)

        assert resp["data"]["tabs"] is handler_tabs
