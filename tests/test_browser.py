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
