"""CLI client (Typer): resolves flags, starts the daemon if needed, sends commands."""

from __future__ import annotations

import json
import sys
import time
from typing import Annotated, cast

import typer

from . import operations as ops
from .models import (
    BackCommand,
    CheckCommand,
    ClickCommand,
    CloseCommand,
    CloseParams,
    CloseTabCommand,
    Command,
    CookiesCommand,
    CookiesParams,
    ErrorResponse,
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
    ScrollDirection,
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
)
from .types import Flags, Tab

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def global_options(
    ctx: typer.Context,
    session: Annotated[
        str,
        typer.Option("--session", help="Session name; isolates daemon and profile."),
    ] = "default",
    headed: Annotated[
        bool,
        typer.Option("--headed", help="Run the browser with a visible window."),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout", min=1, help="Daemon idle timeout in seconds before shutdown."
        ),
    ] = 1800,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print raw JSON instead of formatted output."),
    ] = False,
    persistent: Annotated[
        bool,
        typer.Option(
            "--persistent",
            help="Reuse a fixed identity and profile under ~/.camoufox-cli/profiles.",
        ),
    ] = False,
    user_data_dir: Annotated[
        str | None,
        typer.Option(
            "--user-data-dir", help="Explicit profile dir; overrides --persistent."
        ),
    ] = None,
    proxy: Annotated[
        str | None,
        typer.Option("--proxy", help="Proxy URL passed to the browser."),
    ] = None,
    geoip: Annotated[
        bool,
        typer.Option(
            " /--no-geoip",
            help="Spoof geolocation from the proxy's GeoIP; --no-geoip disables it.",
        ),
    ] = True,
    locale: Annotated[
        str | None,
        typer.Option("--locale", help="Browser locale, e.g. en-US."),
    ] = None,
) -> None:
    """Anti-detect browser CLI & Skills for AI agents, powered by Camoufox."""
    if user_data_dir is not None:
        resolved: str | None = user_data_dir
    elif persistent:
        resolved = ops.get_profile_path(session)
    else:
        resolved = None
    ctx.obj = Flags(
        session=session,
        headed=headed,
        timeout=timeout,
        json=json_output,
        persistent=resolved,
        proxy=proxy,
        geoip=geoip,
        locale=locale,
    )


def _run(ctx: typer.Context, command: Command) -> None:
    f = cast(Flags, ctx.obj)
    ops.ensure_daemon(
        f.session, f.headed, f.timeout, f.persistent, f.proxy, f.geoip, f.locale
    )
    sock = ops.get_socket_path(f.session)
    last_err = ""
    for attempt in range(5):
        try:
            response = ops.send_command(sock, command)
            print_response(response, f.json)
            return
        except ops.ResponseError as e:
            # Command was already delivered; the daemon may have executed it.
            # Retrying would re-run a possibly non-idempotent action.
            print(
                f"Error: command sent but reply failed ({e}); "
                + "not retrying to avoid re-running the action.",
                file=sys.stderr,
            )
            raise typer.Exit(1) from e
        except Exception as e:
            last_err = str(e)
            if attempt < 4:
                time.sleep(0.2 * (attempt + 1))
    print(
        f"Error: Failed to connect to daemon after 5 attempts: {last_err}",
        file=sys.stderr,
    )
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


@app.command(name="open")
def open_(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="URL to navigate to.")],
) -> None:
    """Open a URL, launching the browser if needed."""
    _run(ctx, OpenCommand(id="r1", params=OpenParams(url=url)))


@app.command()
def back(ctx: typer.Context) -> None:
    """Go back in history."""
    _run(ctx, BackCommand(id="r1"))


@app.command()
def forward(ctx: typer.Context) -> None:
    """Go forward in history."""
    _run(ctx, ForwardCommand(id="r1"))


@app.command()
def reload(ctx: typer.Context) -> None:
    """Reload the current page."""
    _run(ctx, ReloadCommand(id="r1"))


@app.command()
def url(ctx: typer.Context) -> None:
    """Print the current page URL."""
    _run(ctx, UrlCommand(id="r1"))


@app.command()
def title(ctx: typer.Context) -> None:
    """Print the current page title."""
    _run(ctx, TitleCommand(id="r1"))


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


@app.command()
def snapshot(
    ctx: typer.Context,
    interactive: Annotated[
        bool,
        typer.Option("-i", "--interactive", help="List interactive elements only."),
    ] = False,
    selector: Annotated[
        str | None,
        typer.Option(
            "-s", "--selector", help="Scope to a CSS selector (default: body)."
        ),
    ] = None,
) -> None:
    """Print the page aria tree with @ref ids for interaction commands."""
    _run(
        ctx,
        SnapshotCommand(
            id="r1",
            params=SnapshotParams(interactive=interactive, selector=selector),
        ),
    )


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------


@app.command()
def click(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Element @ref from snapshot.")],
) -> None:
    """Click the element at a snapshot @ref."""
    _run(ctx, ClickCommand(id="r1", params=RefParams(ref=ref)))


@app.command()
def check(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Element @ref from snapshot.")],
) -> None:
    """Toggle a checkbox or radio at a snapshot @ref."""
    _run(ctx, CheckCommand(id="r1", params=RefParams(ref=ref)))


@app.command()
def hover(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Element @ref from snapshot.")],
) -> None:
    """Hover over the element at a snapshot @ref."""
    _run(ctx, HoverCommand(id="r1", params=RefParams(ref=ref)))


@app.command()
def fill(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Element @ref from snapshot.")],
    text: Annotated[str, typer.Argument(help="Text to enter.")],
) -> None:
    """Clear a field and type text into a snapshot @ref."""
    _run(ctx, FillCommand(id="r1", params=RefTextParams(ref=ref, text=text)))


@app.command(name="type")
def type_(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Element @ref from snapshot.")],
    text: Annotated[str, typer.Argument(help="Text to type.")],
) -> None:
    """Type text into a snapshot @ref without clearing it first."""
    _run(ctx, TypeCommand(id="r1", params=RefTextParams(ref=ref, text=text)))


@app.command()
def select(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Element @ref from snapshot.")],
    value: Annotated[str, typer.Argument(help="Option label to select.")],
) -> None:
    """Select a dropdown option by its visible label."""
    _run(ctx, SelectCommand(id="r1", params=SelectParams(ref=ref, value=value)))


@app.command()
def press(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key or combo, e.g. Enter or Control+a.")],
) -> None:
    """Press a keyboard key or combination."""
    _run(ctx, PressCommand(id="r1", params=PressParams(key=key)))


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------


@app.command()
def text(
    ctx: typer.Context,
    target: Annotated[str, typer.Argument(help="Snapshot @ref or CSS selector.")],
) -> None:
    """Print the text content of an element."""
    _run(ctx, TextCommand(id="r1", params=TextParams(target=target)))


@app.command(name="eval")
def eval_(
    ctx: typer.Context,
    expression: Annotated[
        str, typer.Argument(help="JavaScript expression to evaluate.")
    ],
) -> None:
    """Evaluate a JavaScript expression in the page and print its result."""
    _run(ctx, EvalCommand(id="r1", params=EvalParams(expression=expression)))


@app.command()
def screenshot(
    ctx: typer.Context,
    path: Annotated[
        str | None,
        typer.Argument(help="Output file; omit to return base64 JSON."),
    ] = None,
    full: Annotated[
        bool, typer.Option("--full", help="Capture the full scrollable page.")
    ] = False,
) -> None:
    """Capture a screenshot to a file or as base64 JSON."""
    _run(
        ctx,
        ScreenshotCommand(id="r1", params=ScreenshotParams(path=path, full_page=full)),
    )


@app.command()
def pdf(
    ctx: typer.Context,
    path: Annotated[str, typer.Argument(help="Output PDF file path.")],
) -> None:
    """Save the current page as a PDF."""
    _run(ctx, PdfCommand(id="r1", params=PathParams(path=path)))


# ---------------------------------------------------------------------------
# Scroll & Wait
# ---------------------------------------------------------------------------


@app.command()
def scroll(
    ctx: typer.Context,
    direction: Annotated[
        ScrollDirection, typer.Argument(help="Direction: up, down, left, or right.")
    ],
    amount: Annotated[
        int, typer.Argument(min=1, help="Distance in pixels (default 500).")
    ] = 500,
) -> None:
    """Scroll the page in a direction."""
    _run(
        ctx,
        ScrollCommand(id="r1", params=ScrollParams(direction=direction, amount=amount)),
    )


@app.command()
def wait(
    ctx: typer.Context,
    target: Annotated[
        str | None,
        typer.Argument(help="Snapshot @ref, milliseconds, or CSS selector."),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Wait for a URL glob pattern, e.g. */dashboard."),
    ] = None,
) -> None:
    """Wait for a snapshot @ref, a delay, a selector, or a URL pattern."""
    if url is not None:
        params = WaitParams(url=url)
    elif target is None:
        raise typer.BadParameter(
            "provide @ref, milliseconds, a selector, or --url <pattern>"
        )
    elif target.startswith("@"):
        params = WaitParams(ref=target)
    elif target[0].isdigit():
        try:
            ms = int(target)
        except ValueError:
            raise typer.BadParameter(
                f"wait duration must be an integer, got '{target}'"
            ) from None
        if ms < 1:
            raise typer.BadParameter("wait duration must be >= 1")
        params = WaitParams(ms=ms)
    else:
        params = WaitParams(selector=target)
    _run(ctx, WaitCommand(id="r1", params=params))


# ---------------------------------------------------------------------------
# Tab management
# ---------------------------------------------------------------------------


@app.command()
def tabs(ctx: typer.Context) -> None:
    """List open tabs."""
    _run(ctx, TabsCommand(id="r1"))


@app.command()
def switch(
    ctx: typer.Context,
    index: Annotated[int, typer.Argument(help="Zero-based tab index from `tabs`.")],
) -> None:
    """Switch to the tab at a zero-based index."""
    _run(ctx, SwitchCommand(id="r1", params=SwitchParams(index=index)))


@app.command(name="close-tab")
def close_tab(ctx: typer.Context) -> None:
    """Close the current tab."""
    _run(ctx, CloseTabCommand(id="r1"))


# ---------------------------------------------------------------------------
# Client-side commands (never reach the daemon via _run)
# ---------------------------------------------------------------------------


@app.command()
def install(
    with_deps: Annotated[
        bool,
        typer.Option("--with-deps", help="Also install system libraries (Linux only)."),
    ] = False,
) -> None:
    """Download the Camoufox browser."""
    ops.install_browser(with_deps)


@app.command()
def sessions(
    ctx: typer.Context,
    persistent: Annotated[
        bool,
        typer.Option("--persistent", help="List on-disk persistent profiles instead."),
    ] = False,
) -> None:
    """List active sessions, or persistent profiles with --persistent."""
    f = cast(Flags, ctx.obj)
    names = ops.list_persistent_sessions() if persistent else ops.list_sessions()
    if f.json:
        print(json.dumps(names, indent=2))
    elif not names:
        print("No persistent profiles." if persistent else "No active sessions.")
    else:
        if persistent:
            print(f"From {ops.PROFILES_DIR}/:\n")
        for s in names:
            print(f"  {s}" if persistent else s)


@app.command()
def close(
    ctx: typer.Context,
    all_: Annotated[
        bool, typer.Option("--all", help="Close every active session instead.")
    ] = False,
) -> None:
    """Close the current session's browser and daemon."""
    if all_:
        results = ops.close_all_sessions()
        if not results:
            print("No active sessions.")
            return
        for session, err in results:
            if err:
                print(f"Failed to close session {session}: {err}", file=sys.stderr)
        return
    _run(ctx, CloseCommand(id="r1", params=CloseParams()))


# ---------------------------------------------------------------------------
# Cookies sub-app
# ---------------------------------------------------------------------------

cookies_app = typer.Typer(help="Manage browser cookies.")
app.add_typer(cookies_app, name="cookies")


@cookies_app.command(name="list")
def cookies_list(ctx: typer.Context) -> None:
    """Dump cookies as JSON."""
    _run(ctx, CookiesCommand(id="r1", params=CookiesParams(op="list")))


@cookies_app.command()
def export(
    ctx: typer.Context,
    path: Annotated[str, typer.Argument(help="Destination JSON file (overwritten).")],
) -> None:
    """Export cookies to a JSON file."""
    _run(ctx, CookiesCommand(id="r1", params=CookiesParams(op="export", path=path)))


@cookies_app.command(name="import")
def import_(
    ctx: typer.Context,
    path: Annotated[str, typer.Argument(help="Source JSON file with a cookie array.")],
) -> None:
    """Import cookies from a JSON file into the browser context."""
    _run(ctx, CookiesCommand(id="r1", params=CookiesParams(op="import", path=path)))


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_response(response: Response, json_mode: bool) -> None:
    if json_mode:
        print(response.model_dump_json(indent=2, exclude_none=True))
        return

    if isinstance(response, ErrorResponse):
        print(f"Error: {response.error}", file=sys.stderr)
        sys.exit(1)

    if response.data is None:
        return

    tabs = response.data.tabs

    data = response.data.model_dump(exclude_none=True)
    if not data:
        return

    # `data` is model_dump() of an extra="allow" ResponseData, so its values are
    # Any by design (free-form/extra keys); the reportAny here is expected.
    if "snapshot" in data:
        print(data["snapshot"])  # pyright: ignore[reportAny]
    elif "text" in data:
        print(data["text"])  # pyright: ignore[reportAny]
    elif "result" in data:
        v = data["result"]  # pyright: ignore[reportAny]
        print(
            "null"
            if v is None
            else json.dumps(v, ensure_ascii=False)
            if not isinstance(v, str)
            else v
        )
    elif data.get("closed"):
        pass  # silent
    elif "url" in data:
        if "title" in data:
            print(data["title"])  # pyright: ignore[reportAny]
        print(data["url"])  # pyright: ignore[reportAny]
    elif "title" in data:
        print(data["title"])  # pyright: ignore[reportAny]
    elif tabs is None:
        print(json.dumps(data, indent=2, ensure_ascii=False))

    if tabs is not None:
        print(_format_tabs(tabs))


def _format_tabs(tabs: list[Tab]) -> str:
    if not tabs:
        return "(no tabs)"
    title_width = max(len(t.get("title") or "") for t in tabs)
    lines: list[str] = []
    for t in tabs:
        marker = "*" if t.get("active") else " "
        title = (t.get("title") or "").ljust(title_width)
        lines.append(f"{marker} {t['index']}  {title}  {t['url']}")
    return "\n".join(lines)


def main() -> None:
    app()
