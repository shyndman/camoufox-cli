"""Tests for BrowserManager tab/page bookkeeping without launching a browser."""

from camoufox_cli.browser import BrowserManager


class FakePage:
    def __init__(self, url):
        self.url = url
        self.closed = False

    def bring_to_front(self):
        pass

    def close(self):
        self.closed = True


class FakeContext:
    def __init__(self, pages):
        self._pages = pages

    @property
    def pages(self):
        return self._pages


def _manager(pages, active):
    manager = BrowserManager.__new__(BrowserManager)
    manager._context = FakeContext(pages)
    manager._page = active
    return manager


class TestCloseCurrentTab:
    def test_normal_close_switches_to_neighbor(self):
        a, b, c = FakePage("https://a"), FakePage("https://b"), FakePage("https://c")
        manager = _manager([a, b, c], c)

        manager.close_current_tab()

        assert c.closed is True
        assert manager._page is b

    def test_external_close_recovers_without_crash(self):
        """Active tab closed externally is not in ctx.pages; promote a survivor."""
        a, b = FakePage("https://a"), FakePage("https://b")
        gone = FakePage("https://gone")
        manager = _manager([a, b], gone)

        manager.close_current_tab()

        assert manager._page in (a, b)
        # The tab is already gone; we must not call close() on it.
        assert gone.closed is False

    def test_refuses_to_close_last_tab(self):
        only = FakePage("https://only")
        manager = _manager([only], only)

        import pytest

        with pytest.raises(RuntimeError, match="last tab"):
            manager.close_current_tab()


class _RecordingContext:
    def __init__(self):
        self.extra_headers_calls = []

    def set_extra_http_headers(self, headers):
        self.extra_headers_calls.append(headers)


class _LaunchPage:
    def __init__(self, context):
        self.context = context


class _LaunchBrowser:
    def __init__(self, context):
        self._context = context

    def new_page(self):
        return _LaunchPage(self._context)


class _FakeCamoufox:
    """Stand-in for camoufox.sync_api.Camoufox capturing launch kwargs."""

    last_kwargs = None

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs
        self._context = _RecordingContext()

    def __enter__(self):
        return _LaunchBrowser(self._context)

    def __exit__(self, *exc):
        return False


class TestProxyCredentialScoping:
    """Regression for issue #1: an authenticated proxy must NOT install a
    context-wide Proxy-Authorization header (which Playwright broadcasts to
    every origin). Native proxy auth via the launch kwarg handles the CONNECT
    tunnel instead."""

    def _launch(self, monkeypatch):
        import camoufox_cli.browser as browser_mod

        monkeypatch.setattr(browser_mod, "_ensure_browser_installed", lambda: None)
        monkeypatch.setattr(browser_mod, "Camoufox", _FakeCamoufox)
        _FakeCamoufox.last_kwargs = None
        mgr = BrowserManager(
            proxy="http://user:secretpass@proxy.example:8899", geoip=False
        )
        mgr.launch(headless=True)
        return mgr

    def test_no_proxy_authorization_header_is_broadcast(self, monkeypatch):
        mgr = self._launch(monkeypatch)
        assert mgr._context.extra_headers_calls == []

    def test_credentials_passed_to_native_proxy_auth(self, monkeypatch):
        self._launch(monkeypatch)
        proxy = _FakeCamoufox.last_kwargs["proxy"]
        assert proxy["username"] == "user"
        assert proxy["password"] == "secretpass"
        assert proxy["server"] == "http://proxy.example:8899"
