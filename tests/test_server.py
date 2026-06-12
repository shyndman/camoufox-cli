import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

import pytest

from camoufox_cli.models import ErrorResponse, OkResponse, ResponseData
from camoufox_cli.server import DaemonServer
from camoufox_cli.types import Tab


def _make_server(tmp_path: Path) -> DaemonServer:
    d = object.__new__(DaemonServer)
    d.socket_path = str(tmp_path / "camoufox.sock")
    d.pid_path = str(tmp_path / "camoufox.pid")
    open(d.socket_path, "w").close()
    with open(d.pid_path, "w") as f:
        _ = f.write("424242")
    return d


class TestCleanupStale:
    def test_permission_error_preserves_live_socket(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        d = _make_server(tmp_path)
        monkeypatch.setattr(os, "kill", _raise(PermissionError))
        with pytest.raises(SystemExit):
            d._cleanup_stale()
        assert os.path.exists(d.socket_path)

    def test_live_process_aborts_and_preserves_socket(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        d = _make_server(tmp_path)

        def _kill(pid: int, sig: int) -> None:
            del pid, sig

        monkeypatch.setattr(os, "kill", _kill)
        with pytest.raises(SystemExit):
            d._cleanup_stale()
        assert os.path.exists(d.socket_path)

    def test_dead_process_removes_stale_socket(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        d = _make_server(tmp_path)
        monkeypatch.setattr(os, "kill", _raise(ProcessLookupError))
        d._cleanup_stale()
        assert not os.path.exists(d.socket_path)

    def test_corrupt_pid_file_removes_stale_socket(self, tmp_path: Path):
        d = _make_server(tmp_path)
        with open(d.pid_path, "w") as f:
            _ = f.write("not-a-pid")
        d._cleanup_stale()
        assert not os.path.exists(d.socket_path)


def _raise(exc: type[Exception]) -> Callable[[int, int], NoReturn]:
    def _kill(pid: int, sig: int) -> NoReturn:
        del pid, sig
        raise exc

    return _kill


class FakeManager:
    def __init__(
        self, pages: list[object], tabs: list[Tab], running: bool = True
    ) -> None:
        self._pages: list[object] = pages
        self._tabs: list[Tab] = tabs
        self._running: bool = running

    @property
    def is_running(self) -> bool:
        return self._running

    def get_context(self) -> SimpleNamespace:
        if not self._running:
            raise RuntimeError("Browser not launched.")
        return SimpleNamespace(pages=self._pages)

    def get_tabs(self) -> list[Tab]:
        return self._tabs


def _inject_server(manager: FakeManager) -> DaemonServer:
    d = object.__new__(DaemonServer)
    d.manager = manager  # pyright: ignore[reportAttributeAccessIssue] - duck-typed test double
    d._last_tab_sig = None
    return d


def _ok(data: dict[str, object] | None = None) -> OkResponse:
    return OkResponse(
        id="r1", data=ResponseData.model_validate(data) if data is not None else None
    )


def _tab(index: int, active: bool, url: str = "https://x", title: str = "T") -> Tab:
    return {"index": index, "url": url, "title": title, "active": active}


class TestInjectTabChanges:
    def test_injects_tab_list_when_set_changes(self):
        pages = [object(), object()]
        tabs = [_tab(0, True), _tab(1, False)]
        d = _inject_server(FakeManager(pages, tabs))

        resp = _ok()
        d._inject_tab_changes(resp)

        assert resp.data is not None
        assert resp.data.tabs == tabs

    def test_does_not_reinject_when_set_unchanged(self):
        pages = [object(), object()]
        d = _inject_server(FakeManager(pages, [_tab(0, True)]))

        first = _ok()
        d._inject_tab_changes(first)
        assert first.data is not None and first.data.tabs is not None

        second = _ok()
        d._inject_tab_changes(second)
        assert second.data is None or second.data.tabs is None

    def test_skips_when_browser_not_running(self):
        d = _inject_server(FakeManager([], [], running=False))

        resp = _ok()
        d._inject_tab_changes(resp)

        assert resp.data is None or resp.data.tabs is None

    def test_skips_on_failed_response(self):
        pages = [object()]
        d = _inject_server(FakeManager(pages, [_tab(0, True)]))

        resp = ErrorResponse(id="r1", error="boom")
        d._inject_tab_changes(resp)

        assert isinstance(resp, ErrorResponse)

    def test_does_not_overwrite_handler_tab_list(self):
        """A tab command already carries its own list; injection must not clobber it."""
        pages = [object()]
        handler_tabs = [_tab(0, True, url="https://handler")]
        d = _inject_server(FakeManager(pages, [_tab(0, False)]))

        resp = _ok({"tabs": handler_tabs})
        d._inject_tab_changes(resp)

        assert resp.data is not None
        assert resp.data.tabs == handler_tabs
