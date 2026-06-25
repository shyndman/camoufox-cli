"""In-process structural types.

These describe shapes we *construct* in-process and never parse from an
untrusted source, so a TypedDict / dataclass is enough — no validation needed.
Anything that crosses a trust boundary (socket, disk, external lib) lives in
``models.py`` as a Pydantic model instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class Tab(TypedDict):
    """One open browser tab, as surfaced by ``BrowserManager.get_tabs``."""

    index: int
    url: str
    title: str
    active: bool


class _ProxyBase(TypedDict):
    server: str


class ProxySettings(_ProxyBase, total=False):
    """Playwright/Camoufox proxy kwarg. ``server`` always present; credentials
    only when the proxy URL carried them."""

    username: str
    password: str


@dataclass
class Flags:
    """Parsed CLI flags (the non-command half of ``parse_args``).

    Config we build ourselves from argv — a dataclass, not wire data.
    """

    session: str = "default"
    headed: bool = False
    timeout: int = 1800
    json: bool = False
    persistent: str | None = None
    proxy: str | None = None
    geoip: bool = True
    locale: str | None = None
    clone_from: str | None = None
