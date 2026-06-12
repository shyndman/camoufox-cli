"""Command implementations for the daemon."""

from __future__ import annotations

import base64
import io
import json

from pydantic import ValidationError

from .browser import BrowserManager
from .models import (
    BackCommand,
    CheckCommand,
    ClickCommand,
    CloseCommand,
    CloseTabCommand,
    Command,
    CookiesCommand,
    CookiesParams,
    EvalCommand,
    EvalParams,
    FillCommand,
    ForwardCommand,
    HoverCommand,
    OpenCommand,
    OpenParams,
    PathParams,
    PdfCommand,
    PressCommand,
    PressParams,
    RefParams,
    RefTextParams,
    ReloadCommand,
    Response,
    ScreenshotCommand,
    ScreenshotParams,
    ScrollCommand,
    ScrollParams,
    SelectCommand,
    SelectParams,
    SnapshotCommand,
    SnapshotParams,
    SwitchCommand,
    SwitchParams,
    TabsCommand,
    TextCommand,
    TextParams,
    TitleCommand,
    TypeCommand,
    UrlCommand,
    WaitCommand,
    WaitParams,
    command_adapter,
)
from .protocol import error_response, ok_response

# Actions the daemon can execute. ``install`` / ``sessions`` are valid commands
# but handled CLI-side; if they reach the daemon they're treated as unknown.
_DAEMON_ACTIONS = frozenset({
    "open", "back", "forward", "reload", "url", "title", "close",
    "snapshot", "click", "fill", "type", "select", "check", "hover", "press",
    "text", "eval", "screenshot", "pdf", "scroll", "wait",
    "tabs", "switch", "close-tab", "cookies",
})


def execute(
    manager: BrowserManager, raw: dict[str, object], headless: bool | None = None
) -> Response:
    """Validate a raw command, dispatch it, and return a response.

    Validation lives here (not at the socket read) so a malformed or unknown
    command becomes a graceful error response instead of crashing the daemon.
    ``headless`` is the daemon's own launch mode, applied to ``open`` so the
    client cannot dictate it.
    """
    cmd_id = str(raw.get("id", "?"))
    action = raw.get("action")
    if action not in _DAEMON_ACTIONS:
        return error_response(cmd_id, f"Unknown action: {action}")

    try:
        command = command_adapter.validate_python(raw)
    except ValidationError as e:
        return error_response(cmd_id, _format_validation_error(e))

    if isinstance(command, OpenCommand) and headless is not None:
        command.params.headless = headless

    try:
        return _dispatch(manager, command)
    except Exception as e:
        return error_response(command.id, str(e))


def _format_validation_error(e: ValidationError) -> str:
    err = e.errors()[0]
    loc = ".".join(str(p) for p in err["loc"]) or "command"
    return f"Invalid command ({loc}): {err['msg']}"


def _dispatch(manager: BrowserManager, command: Command) -> Response:
    cmd_id = command.id
    match command:
        case OpenCommand():
            return _cmd_open(manager, cmd_id, command.params)
        case BackCommand():
            return _cmd_back(manager, cmd_id)
        case ForwardCommand():
            return _cmd_forward(manager, cmd_id)
        case ReloadCommand():
            return _cmd_reload(manager, cmd_id)
        case UrlCommand():
            return _cmd_url(manager, cmd_id)
        case TitleCommand():
            return _cmd_title(manager, cmd_id)
        case CloseCommand():
            return _cmd_close(manager, cmd_id)
        case SnapshotCommand():
            return _cmd_snapshot(manager, cmd_id, command.params)
        case ClickCommand():
            return _cmd_click(manager, cmd_id, command.params)
        case FillCommand():
            return _cmd_fill(manager, cmd_id, command.params)
        case TypeCommand():
            return _cmd_type(manager, cmd_id, command.params)
        case SelectCommand():
            return _cmd_select(manager, cmd_id, command.params)
        case CheckCommand():
            return _cmd_check(manager, cmd_id, command.params)
        case HoverCommand():
            return _cmd_hover(manager, cmd_id, command.params)
        case PressCommand():
            return _cmd_press(manager, cmd_id, command.params)
        case TextCommand():
            return _cmd_text(manager, cmd_id, command.params)
        case EvalCommand():
            return _cmd_eval(manager, cmd_id, command.params)
        case ScreenshotCommand():
            return _cmd_screenshot(manager, cmd_id, command.params)
        case PdfCommand():
            return _cmd_pdf(manager, cmd_id, command.params)
        case ScrollCommand():
            return _cmd_scroll(manager, cmd_id, command.params)
        case WaitCommand():
            return _cmd_wait(manager, cmd_id, command.params)
        case TabsCommand():
            return _cmd_tabs(manager, cmd_id)
        case SwitchCommand():
            return _cmd_switch(manager, cmd_id, command.params)
        case CloseTabCommand():
            return _cmd_close_tab(manager, cmd_id)
        case CookiesCommand():
            return _cmd_cookies(manager, cmd_id, command.params)
        case _:
            return error_response(command.id, f"Unknown action: {command.action}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_ref(manager: BrowserManager, ref_str: str):
    """Resolve a ref string to a locator, or raise."""
    entry = manager.refs.resolve(ref_str)
    if entry is None:
        raise ValueError(f"Ref @{ref_str.lstrip('@')} not found. Run 'camoufox-cli snapshot' to refresh refs.")
    page = manager.get_page()
    if entry.name:
        locator = page.get_by_role(entry.role, name=entry.name, exact=True)  # type: ignore[arg-type]
    else:
        locator = page.get_by_role(entry.role)  # type: ignore[arg-type]
    return locator.nth(entry.nth)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def _cmd_open(manager: BrowserManager, cmd_id: str, params: OpenParams) -> Response:
    url = params.url
    if not url:
        return error_response(cmd_id, "Missing 'url' parameter")

    if not manager.is_running:
        manager.launch(headless=params.headless)

    try:
        page = manager.get_page()
        page.goto(url, wait_until="domcontentloaded")
    except Exception as e:
        if "has been closed" in str(e):
            # Browser crashed or was closed externally — relaunch
            manager.close()
            manager.launch(headless=params.headless)
            page = manager.get_page()
            page.goto(url, wait_until="domcontentloaded")
        else:
            raise

    manager.push_history(page.url)
    return ok_response(cmd_id, {"url": page.url, "title": page.title()})


def _cmd_back(manager: BrowserManager, cmd_id: str) -> Response:
    url = manager.go_back()
    if url is None:
        return error_response(cmd_id, "No previous page in history")
    page = manager.get_page()
    return ok_response(cmd_id, {"url": page.url, "title": page.title()})


def _cmd_forward(manager: BrowserManager, cmd_id: str) -> Response:
    url = manager.go_forward()
    if url is None:
        return error_response(cmd_id, "No next page in history")
    page = manager.get_page()
    return ok_response(cmd_id, {"url": page.url, "title": page.title()})


def _cmd_reload(manager: BrowserManager, cmd_id: str) -> Response:
    page = manager.get_page()
    page.goto(page.url, wait_until="domcontentloaded")
    return ok_response(cmd_id)


def _cmd_url(manager: BrowserManager, cmd_id: str) -> Response:
    return ok_response(cmd_id, {"url": manager.get_page().url})


def _cmd_title(manager: BrowserManager, cmd_id: str) -> Response:
    return ok_response(cmd_id, {"title": manager.get_page().title()})


def _cmd_close(manager: BrowserManager, cmd_id: str) -> Response:
    manager.close()
    return ok_response(cmd_id, {"closed": True})


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def _cmd_snapshot(manager: BrowserManager, cmd_id: str, params: SnapshotParams) -> Response:
    page = manager.get_page()
    target = page.locator(params.selector) if params.selector else page.locator("body")
    aria_text = target.aria_snapshot()
    annotated = manager.refs.build_from_snapshot(aria_text, interactive_only=params.interactive)
    return ok_response(cmd_id, {"snapshot": annotated})


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------

def _cmd_click(manager: BrowserManager, cmd_id: str, params: RefParams) -> Response:
    if not params.ref:
        return error_response(cmd_id, "Missing 'ref' parameter")
    locator = _resolve_ref(manager, params.ref)
    page = manager.get_page()
    url_before = page.url

    # Issue real trusted click (force=True bypasses the actionability check, so
    # sticky headers/overlays intercepting pointer events no longer time it out).
    # A real click fires onclick/JS/SPA/hash handlers AND performs default
    # navigation for plain links, unlike the old page.goto() path which skipped
    # handlers and broke JS/hash/SPA links. Camoufox still silently drops
    # target="_blank" clicks, so those are navigated explicitly via page.goto().
    blank_href = locator.evaluate(
        "el => { const a = el.closest('a'); return a && a.target === '_blank' ? a.href : null; }"
    )
    if blank_href:
        page.goto(blank_href, wait_until="domcontentloaded")
    else:
        locator.click(force=True)

    url_after = page.url
    if url_after != url_before:
        manager.push_history(url_after)
    return ok_response(cmd_id)


def _cmd_fill(manager: BrowserManager, cmd_id: str, params: RefTextParams) -> Response:
    if not params.ref:
        return error_response(cmd_id, "Missing 'ref' parameter")
    _resolve_ref(manager, params.ref).fill(params.text)
    return ok_response(cmd_id)


def _cmd_type(manager: BrowserManager, cmd_id: str, params: RefTextParams) -> Response:
    if not params.ref:
        return error_response(cmd_id, "Missing 'ref' parameter")
    _resolve_ref(manager, params.ref).press_sequentially(params.text)
    return ok_response(cmd_id)


def _cmd_select(manager: BrowserManager, cmd_id: str, params: SelectParams) -> Response:
    if not params.ref:
        return error_response(cmd_id, "Missing 'ref' parameter")
    _resolve_ref(manager, params.ref).select_option(label=params.value)
    return ok_response(cmd_id)


def _cmd_check(manager: BrowserManager, cmd_id: str, params: RefParams) -> Response:
    if not params.ref:
        return error_response(cmd_id, "Missing 'ref' parameter")
    locator = _resolve_ref(manager, params.ref)
    if locator.is_checked():
        locator.uncheck(force=True)
    else:
        locator.check(force=True)
    return ok_response(cmd_id)


def _cmd_hover(manager: BrowserManager, cmd_id: str, params: RefParams) -> Response:
    if not params.ref:
        return error_response(cmd_id, "Missing 'ref' parameter")
    _resolve_ref(manager, params.ref).hover(force=True)
    return ok_response(cmd_id)


def _cmd_press(manager: BrowserManager, cmd_id: str, params: PressParams) -> Response:
    if not params.key:
        return error_response(cmd_id, "Missing 'key' parameter")
    manager.get_page().keyboard.press(params.key)
    return ok_response(cmd_id)


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def _cmd_text(manager: BrowserManager, cmd_id: str, params: TextParams) -> Response:
    target = params.target
    if not target:
        return error_response(cmd_id, "Missing 'target' parameter")

    if target.startswith("@"):
        text = _resolve_ref(manager, target).text_content() or ""
    else:
        text = manager.get_page().locator(target).text_content() or ""

    return ok_response(cmd_id, {"text": text})


def _cmd_eval(manager: BrowserManager, cmd_id: str, params: EvalParams) -> Response:
    if not params.expression:
        return error_response(cmd_id, "Missing 'expression' parameter")
    result = manager.get_page().evaluate(params.expression)
    return ok_response(cmd_id, {"result": result})


def _cmd_screenshot(manager: BrowserManager, cmd_id: str, params: ScreenshotParams) -> Response:
    page = manager.get_page()
    if params.path:
        page.screenshot(path=params.path, full_page=params.full_page)
        return ok_response(cmd_id, {"path": params.path})
    else:
        buf = page.screenshot(full_page=params.full_page)
        b64 = base64.b64encode(buf).decode("ascii")
        return ok_response(cmd_id, {"base64": b64})


def _cmd_pdf(manager: BrowserManager, cmd_id: str, params: PathParams) -> Response:
    if not params.path:
        return error_response(cmd_id, "Missing 'path' parameter")

    page = manager.get_page()
    buf = page.screenshot(full_page=True)

    from PIL import Image

    img = Image.open(io.BytesIO(buf))
    if img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(params.path, "PDF", resolution=72.0)

    return ok_response(cmd_id, {"path": params.path})


# ---------------------------------------------------------------------------
# Scroll & Wait
# ---------------------------------------------------------------------------

def _cmd_scroll(manager: BrowserManager, cmd_id: str, params: ScrollParams) -> Response:
    amount = -params.amount if params.direction == "up" else params.amount
    manager.get_page().evaluate(f"window.scrollBy(0, {amount})")
    return ok_response(cmd_id)


def _cmd_wait(manager: BrowserManager, cmd_id: str, params: WaitParams) -> Response:
    page = manager.get_page()

    if params.ms is not None:
        page.wait_for_timeout(params.ms)
    elif params.ref:
        _resolve_ref(manager, params.ref).wait_for()
    elif params.selector:
        page.wait_for_selector(params.selector)
    elif params.url:
        page.wait_for_url(params.url)
    else:
        return error_response(cmd_id, "wait requires ms, ref, selector, or url parameter")

    return ok_response(cmd_id)


# ---------------------------------------------------------------------------
# Tab management
# ---------------------------------------------------------------------------

def _cmd_tabs(manager: BrowserManager, cmd_id: str) -> Response:
    return ok_response(cmd_id, {"tabs": manager.get_tabs()})


def _cmd_switch(manager: BrowserManager, cmd_id: str, params: SwitchParams) -> Response:
    manager.switch_to_tab(params.index)
    return ok_response(cmd_id, {"tabs": manager.get_tabs()})


def _cmd_close_tab(manager: BrowserManager, cmd_id: str) -> Response:
    manager.close_current_tab()
    return ok_response(cmd_id, {"tabs": manager.get_tabs()})


# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------

def _cmd_cookies(manager: BrowserManager, cmd_id: str, params: CookiesParams) -> Response:
    ctx = manager.get_context()
    op = params.op

    if op == "list":
        cookies = ctx.cookies()
        return ok_response(cmd_id, {"cookies": cookies})

    elif op == "export":
        if not params.path:
            return error_response(cmd_id, "Missing 'path' parameter for export")
        cookies = ctx.cookies()
        with open(params.path, "w") as f:
            json.dump(cookies, f, indent=2)
        return ok_response(cmd_id, {"path": params.path, "count": len(cookies)})

    else:  # "import" — the only remaining Literal value
        if not params.path:
            return error_response(cmd_id, "Missing 'path' parameter for import")
        with open(params.path) as f:
            cookies = json.load(f)
        ctx.add_cookies(cookies)
        return ok_response(cmd_id, {"count": len(cookies)})
