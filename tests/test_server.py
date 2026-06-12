import os

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
