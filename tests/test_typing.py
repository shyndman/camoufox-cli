from typing import cast

import pytest

from camoufox_cli import commands
from camoufox_cli.browser import BrowserManager
from camoufox_cli.models import RefTextParams


class _FakeLocator:
    def __init__(self) -> None:
        self.presses: list[tuple[str, float | None]] = []
        self.seq: str | None = None
        self.filled: list[str] = []

    def press(self, key: str, delay: float | None = None) -> None:
        self.presses.append((key, delay))

    def press_sequentially(self, text: str) -> None:
        self.seq = text

    def fill(self, text: str) -> None:
        self.filled.append(text)


def _mgr() -> BrowserManager:
    return cast(BrowserManager, object())


def _patch_resolve(monkeypatch: pytest.MonkeyPatch, fake: _FakeLocator) -> None:
    def resolve(_manager: BrowserManager, _ref: str) -> _FakeLocator:
        return fake

    monkeypatch.setattr(commands, "_resolve_ref", resolve)


def test_type_humanized_presses_with_dwell(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeLocator()
    _patch_resolve(monkeypatch, fake)
    _ = commands._cmd_type(_mgr(), "r1", RefTextParams(ref="@e1", text="hi there"))
    assert fake.seq is None
    assert fake.presses and all(d is not None for _, d in fake.presses)


def test_type_no_humanize_uses_press_sequentially(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeLocator()
    _patch_resolve(monkeypatch, fake)
    _ = commands._cmd_type(
        _mgr(), "r1", RefTextParams(ref="@e1", text="hi", humanize=False)
    )
    assert fake.seq == "hi"
    assert not fake.presses


def test_fill_humanized_clears_then_types(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeLocator()
    _patch_resolve(monkeypatch, fake)
    _ = commands._cmd_fill(_mgr(), "r1", RefTextParams(ref="@e1", text="abc"))
    assert fake.filled == [""]
    assert fake.presses


def test_fill_no_humanize_sets_value(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeLocator()
    _patch_resolve(monkeypatch, fake)
    _ = commands._cmd_fill(
        _mgr(), "r1", RefTextParams(ref="@e1", text="abc", humanize=False)
    )
    assert fake.filled == ["abc"]
    assert not fake.presses
