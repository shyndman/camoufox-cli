"""CLI client (Typer): resolves flags, starts the daemon if needed, sends commands."""

from __future__ import annotations

import json
import os
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
    session: Annotated[str, typer.Option("--session")] = "default",
    headed: Annotated[bool, typer.Option("--headed")] = False,
    timeout: Annotated[int, typer.Option("--timeout", min=1)] = 1800,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    persistent: Annotated[bool, typer.Option("--persistent")] = False,
    user_data_dir: Annotated[str | None, typer.Option("--user-data-dir")] = None,
    proxy: Annotated[str | None, typer.Option("--proxy")] = None,
    geoip: Annotated[bool, typer.Option(" /--no-geoip")] = True,
    locale: Annotated[str | None, typer.Option("--locale")] = None,
) -> None:
    if user_data_dir is not None:
        resolved: str | None = user_data_dir
    elif persistent:
        resolved = os.path.expanduser(f"~/.camoufox-cli/profiles/{session}")
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
def open_(ctx: typer.Context, url: str) -> None:
    _run(ctx, OpenCommand(id="r1", params=OpenParams(url=url)))


@app.command()
def back(ctx: typer.Context) -> None:
    _run(ctx, BackCommand(id="r1"))


@app.command()
def forward(ctx: typer.Context) -> None:
    _run(ctx, ForwardCommand(id="r1"))


@app.command()
def reload(ctx: typer.Context) -> None:
    _run(ctx, ReloadCommand(id="r1"))


@app.command()
def url(ctx: typer.Context) -> None:
    _run(ctx, UrlCommand(id="r1"))


@app.command()
def title(ctx: typer.Context) -> None:
    _run(ctx, TitleCommand(id="r1"))


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


@app.command()
def snapshot(
    ctx: typer.Context,
    interactive: Annotated[bool, typer.Option("-i", "--interactive")] = False,
    selector: Annotated[str | None, typer.Option("-s", "--selector")] = None,
) -> None:
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
def click(ctx: typer.Context, ref: str) -> None:
    _run(ctx, ClickCommand(id="r1", params=RefParams(ref=ref)))


@app.command()
def check(ctx: typer.Context, ref: str) -> None:
    _run(ctx, CheckCommand(id="r1", params=RefParams(ref=ref)))


@app.command()
def hover(ctx: typer.Context, ref: str) -> None:
    _run(ctx, HoverCommand(id="r1", params=RefParams(ref=ref)))


@app.command()
def fill(ctx: typer.Context, ref: str, text: str) -> None:
    _run(ctx, FillCommand(id="r1", params=RefTextParams(ref=ref, text=text)))


@app.command(name="type")
def type_(ctx: typer.Context, ref: str, text: str) -> None:
    _run(ctx, TypeCommand(id="r1", params=RefTextParams(ref=ref, text=text)))


@app.command()
def select(ctx: typer.Context, ref: str, value: str) -> None:
    _run(ctx, SelectCommand(id="r1", params=SelectParams(ref=ref, value=value)))


@app.command()
def press(ctx: typer.Context, key: str) -> None:
    _run(ctx, PressCommand(id="r1", params=PressParams(key=key)))


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------


@app.command()
def text(ctx: typer.Context, target: str) -> None:
    _run(ctx, TextCommand(id="r1", params=TextParams(target=target)))


@app.command(name="eval")
def eval_(ctx: typer.Context, expression: str) -> None:
    _run(ctx, EvalCommand(id="r1", params=EvalParams(expression=expression)))


@app.command()
def screenshot(
    ctx: typer.Context,
    path: Annotated[str | None, typer.Argument()] = None,
    full: Annotated[bool, typer.Option("--full")] = False,
) -> None:
    _run(
        ctx,
        ScreenshotCommand(id="r1", params=ScreenshotParams(path=path, full_page=full)),
    )


@app.command()
def pdf(ctx: typer.Context, path: str) -> None:
    _run(ctx, PdfCommand(id="r1", params=PathParams(path=path)))


# ---------------------------------------------------------------------------
# Scroll & Wait
# ---------------------------------------------------------------------------


@app.command()
def scroll(
    ctx: typer.Context,
    direction: ScrollDirection,
    amount: Annotated[int, typer.Argument(min=1)] = 500,
) -> None:
    _run(
        ctx,
        ScrollCommand(id="r1", params=ScrollParams(direction=direction, amount=amount)),
    )


@app.command()
def wait(
    ctx: typer.Context,
    target: Annotated[str | None, typer.Argument()] = None,
    url: Annotated[str | None, typer.Option("--url")] = None,
) -> None:
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
    _run(ctx, TabsCommand(id="r1"))


@app.command()
def switch(ctx: typer.Context, index: int) -> None:
    _run(ctx, SwitchCommand(id="r1", params=SwitchParams(index=index)))


@app.command(name="close-tab")
def close_tab(ctx: typer.Context) -> None:
    _run(ctx, CloseTabCommand(id="r1"))


# ---------------------------------------------------------------------------
# Client-side commands (never reach the daemon via _run)
# ---------------------------------------------------------------------------


@app.command()
def install(with_deps: Annotated[bool, typer.Option("--with-deps")] = False) -> None:
    ops.install_browser(with_deps)


@app.command()
def sessions(ctx: typer.Context) -> None:
    f = cast(Flags, ctx.obj)
    names = ops.list_sessions()
    if f.json:
        print(json.dumps(names, indent=2))
    elif not names:
        print("No active sessions.")
    else:
        for s in names:
            print(s)


@app.command()
def close(
    ctx: typer.Context,
    all_: Annotated[bool, typer.Option("--all")] = False,
) -> None:
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
    _run(ctx, CookiesCommand(id="r1", params=CookiesParams(op="list")))


@cookies_app.command()
def export(ctx: typer.Context, path: str) -> None:
    _run(ctx, CookiesCommand(id="r1", params=CookiesParams(op="export", path=path)))


@cookies_app.command(name="import")
def import_(ctx: typer.Context, path: str) -> None:
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
