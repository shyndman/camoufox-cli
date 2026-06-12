"""Tests for BrowserManager tab/page bookkeeping without launching a browser."""

from typing import cast

import pytest
from playwright.sync_api import BrowserContext, Page

from camoufox_cli.browser import BrowserManager
from camoufox_cli.types import ProxySettings


class FakePage:
    def __init__(self, url: str) -> None:
        self.url: str = url
        self.closed: bool = False

    def bring_to_front(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, pages: list[FakePage]) -> None:
        self._pages: list[FakePage] = pages

    @property
    def pages(self) -> list[FakePage]:
        return self._pages


def _manager(pages: list[FakePage], active: FakePage) -> BrowserManager:
    manager = BrowserManager.__new__(BrowserManager)
    # Duck-typed fakes stand in for the real Playwright objects; cast through
    # object since the fakes only implement the slice of API these tests touch.
    manager._context = cast(BrowserContext, cast(object, FakeContext(pages)))
    manager._page = cast(Page, cast(object, active))
    return manager


class TestCloseCurrentTab:
    def test_normal_close_switches_to_neighbor(self) -> None:
        a, b, c = FakePage("https://a"), FakePage("https://b"), FakePage("https://c")
        manager = _manager([a, b, c], c)

        manager.close_current_tab()

        assert c.closed is True
        assert manager.get_page() is b

    def test_external_close_recovers_without_crash(self) -> None:
        """Active tab closed externally is not in ctx.pages; promote a survivor."""
        a, b = FakePage("https://a"), FakePage("https://b")
        gone = FakePage("https://gone")
        manager = _manager([a, b], gone)

        manager.close_current_tab()

        assert manager.get_page() in (a, b)
        # The tab is already gone; we must not call close() on it.
        assert gone.closed is False

    def test_refuses_to_close_last_tab(self) -> None:
        only = FakePage("https://only")
        manager = _manager([only], only)

        with pytest.raises(RuntimeError, match="last tab"):
            manager.close_current_tab()


class _RecordingContext:
    def __init__(self) -> None:
        self.extra_headers_calls: list[dict[str, str]] = []

    def set_extra_http_headers(self, headers: dict[str, str]) -> None:
        self.extra_headers_calls.append(headers)


class _LaunchPage:
    def __init__(self, context: _RecordingContext) -> None:
        self.context: _RecordingContext = context


class _LaunchBrowser:
    def __init__(self, context: _RecordingContext) -> None:
        self._context: _RecordingContext = context

    def new_page(self) -> _LaunchPage:
        return _LaunchPage(self._context)


class _FakeCamoufox:
    """Stand-in for camoufox.sync_api.Camoufox capturing launch kwargs."""

    last_kwargs: "dict[str, object] | None" = None

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = kwargs
        self._context: _RecordingContext = _RecordingContext()

    def __enter__(self) -> _LaunchBrowser:
        return _LaunchBrowser(self._context)

    def __exit__(self, *exc: object) -> bool:
        return False


class TestProxyCredentialScoping:
    """Regression for issue #1: an authenticated proxy must NOT install a
    context-wide Proxy-Authorization header (which Playwright broadcasts to
    every origin). Native proxy auth via the launch kwarg handles the CONNECT
    tunnel instead."""

    def _launch(self, monkeypatch: pytest.MonkeyPatch) -> BrowserManager:
        import camoufox_cli.browser as browser_mod

        monkeypatch.setattr(browser_mod, "_ensure_browser_installed", lambda: None)
        monkeypatch.setattr(browser_mod, "Camoufox", _FakeCamoufox)
        _FakeCamoufox.last_kwargs = None
        mgr = BrowserManager(
            proxy="http://user:secretpass@proxy.example:8899", geoip=False
        )
        mgr.launch(headless=True)
        return mgr

    def test_no_proxy_authorization_header_is_broadcast(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mgr = self._launch(monkeypatch)
        # The fake camoufox wires a _RecordingContext in as the page context.
        context = cast(_RecordingContext, cast(object, mgr.get_context()))
        assert context.extra_headers_calls == []

    def test_credentials_passed_to_native_proxy_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ = self._launch(monkeypatch)
        kwargs = _FakeCamoufox.last_kwargs
        assert kwargs is not None
        proxy = cast(ProxySettings, kwargs["proxy"])
        assert proxy.get("username") == "user"
        assert proxy.get("password") == "secretpass"
        assert proxy["server"] == "http://proxy.example:8899"
