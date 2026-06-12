"""CLI client: parses args, starts daemon if needed, sends command via Unix socket."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time

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
    InstallCommand,
    InstallParams,
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
    SessionsCommand,
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
    response_adapter,
)
from .types import Flags, Tab

SOCKET_PREFIX = "/tmp/camoufox-cli-"


class ResponseError(Exception):
    """Raised when a failure occurs *after* the command was transmitted.

    The daemon may already have executed the (possibly non-idempotent) action,
    so callers MUST NOT retry on this error.
    """

    def __init__(self, cause: Exception):
        super().__init__(str(cause))
        self.cause = cause


def get_socket_path(session: str) -> str:
    return f"{SOCKET_PREFIX}{session}.sock"


def get_log_path(session: str) -> str:
    return f"{SOCKET_PREFIX}{session}.log"


def send_command(sock_path: str, command: Command) -> Response:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall(command_adapter.dump_json(command) + b"\n")
    s.shutdown(socket.SHUT_WR)
    # Past this point the command is on the wire; any failure reading the
    # reply is a ResponseError, never a retryable connect-phase error.
    try:
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        return response_adapter.validate_json(data)
    except Exception as e:
        raise ResponseError(e) from e
    finally:
        s.close()


def spawn_daemon(session: str, headed: bool, timeout: int, persistent: str | None, proxy: str | None = None, geoip: bool = True, locale: str | None = None) -> None:
    cmd = [sys.executable, "-m", "camoufox_cli", "--session", session, "--timeout", str(timeout)]
    if headed:
        cmd.append("--headed")
    if persistent:
        cmd.extend(["--persistent", persistent])
    if proxy:
        cmd.extend(["--proxy", proxy])
    if not geoip:
        cmd.append("--no-geoip")
    if locale:
        cmd.extend(["--locale", locale])

    log_path = get_log_path(session)
    with open(log_path, "ab", buffering=0) as log_file:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    sock_path = get_socket_path(session)
    for _ in range(50):
        if os.path.exists(sock_path):
            return
        time.sleep(0.1)

    print(f"Error: Daemon did not start within 5 seconds; see {log_path}", file=sys.stderr)
    sys.exit(1)


def ensure_daemon(session: str, headed: bool, timeout: int, persistent: str | None, proxy: str | None = None, geoip: bool = True, locale: str | None = None) -> None:
    sock_path = get_socket_path(session)
    if os.path.exists(sock_path):
        # Verify daemon is actually alive by trying to connect
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(sock_path)
            s.close()
            return
        except (ConnectionRefusedError, OSError):
            # Stale socket from a dead daemon — clean up
            try:
                os.unlink(sock_path)
            except FileNotFoundError:
                pass
    spawn_daemon(session, headed, timeout, persistent, proxy, geoip, locale)


def list_sessions() -> list[str]:
    sessions = []
    try:
        for name in os.listdir("/tmp"):
            if name.startswith("camoufox-cli-") and name.endswith(".sock"):
                sessions.append(name[len("camoufox-cli-"):-len(".sock")])
    except OSError:
        pass
    sessions.sort()
    return sessions


def parse_args(args: list[str]) -> tuple[Flags, Command]:
    """Parse CLI args into (flags, command)."""
    flags = Flags()
    rest: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--session":
            i += 1
            if i >= len(args):
                print("Error: --session requires a value", file=sys.stderr)
                sys.exit(1)
            flags.session = args[i]
        elif args[i] == "--headed":
            flags.headed = True
        elif args[i] == "--timeout":
            i += 1
            if i >= len(args):
                print("Error: --timeout requires a value", file=sys.stderr)
                sys.exit(1)
            flags.timeout = _require_int(args[i], "--timeout (daemon idle timeout in seconds)", 1)
        elif args[i] == "--json":
            flags.json = True
        elif args[i] == "--persistent":
            # Optional value: if next arg looks like a path, use it; otherwise use default
            if i + 1 < len(args) and ("/" in args[i + 1] or args[i + 1].startswith((".", "~"))):
                i += 1
                flags.persistent = args[i]
            else:
                flags.persistent = ""
        elif args[i] == "--proxy":
            i += 1
            if i >= len(args):
                print("Error: --proxy requires a value", file=sys.stderr)
                sys.exit(1)
            flags.proxy = args[i]
        elif args[i] == "--no-geoip":
            flags.geoip = False
        elif args[i] == "--locale":
            i += 1
            if i >= len(args):
                print("Error: --locale requires a value", file=sys.stderr)
                sys.exit(1)
            flags.locale = args[i]
        else:
            rest.append(args[i])
        i += 1

    if not rest:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    action = rest[0]
    cmd = build_command(action, rest)
    return flags, cmd


def build_command(action: str, rest: list[str]) -> Command:
    """Build a typed command from action and remaining args."""
    match action:
        # Navigation
        case "open":
            url = _require(rest, 1, "Usage: camoufox-cli open <url>")
            return OpenCommand(id="r1", params=OpenParams(url=url))
        case "back":
            return BackCommand(id="r1")
        case "forward":
            return ForwardCommand(id="r1")
        case "reload":
            return ReloadCommand(id="r1")
        case "url":
            return UrlCommand(id="r1")
        case "title":
            return TitleCommand(id="r1")
        case "close":
            return CloseCommand(id="r1", params=CloseParams(all="--all" in rest))

        # Snapshot
        case "snapshot":
            selector = None
            if "-s" in rest:
                idx = rest.index("-s")
                selector = _require(rest, idx + 1, "Usage: camoufox-cli snapshot -s <selector>")
            return SnapshotCommand(
                id="r1",
                params=SnapshotParams(interactive="-i" in rest, selector=selector),
            )

        # Interaction
        case "click":
            ref = _require(rest, 1, "Usage: camoufox-cli click @e1")
            return ClickCommand(id="r1", params=RefParams(ref=ref))
        case "fill":
            ref = _require(rest, 1, "Usage: camoufox-cli fill @e1 \"text\"")
            text = _require(rest, 2, "Usage: camoufox-cli fill @e1 \"text\"")
            return FillCommand(id="r1", params=RefTextParams(ref=ref, text=text))
        case "type":
            ref = _require(rest, 1, "Usage: camoufox-cli type @e1 \"text\"")
            text = _require(rest, 2, "Usage: camoufox-cli type @e1 \"text\"")
            return TypeCommand(id="r1", params=RefTextParams(ref=ref, text=text))
        case "select":
            ref = _require(rest, 1, "Usage: camoufox-cli select @e1 \"option\"")
            value = _require(rest, 2, "Usage: camoufox-cli select @e1 \"option\"")
            return SelectCommand(id="r1", params=SelectParams(ref=ref, value=value))
        case "check":
            ref = _require(rest, 1, "Usage: camoufox-cli check @e1")
            return CheckCommand(id="r1", params=RefParams(ref=ref))
        case "hover":
            ref = _require(rest, 1, "Usage: camoufox-cli hover @e1")
            return HoverCommand(id="r1", params=RefParams(ref=ref))
        case "press":
            key = _require(rest, 1, "Usage: camoufox-cli press Enter")
            return PressCommand(id="r1", params=PressParams(key=key))

        # Data extraction
        case "text":
            target = _require(rest, 1, "Usage: camoufox-cli text @e1 | camoufox-cli text body")
            return TextCommand(id="r1", params=TextParams(target=target))
        case "eval":
            expr = _require(rest, 1, "Usage: camoufox-cli eval \"document.title\"")
            return EvalCommand(id="r1", params=EvalParams(expression=expr))
        case "screenshot":
            screenshot_params = ScreenshotParams()
            for arg in rest[1:]:
                if arg == "--full":
                    screenshot_params.full_page = True
                else:
                    screenshot_params.path = arg
            return ScreenshotCommand(id="r1", params=screenshot_params)
        case "pdf":
            path = _require(rest, 1, "Usage: camoufox-cli pdf output.pdf")
            return PdfCommand(id="r1", params=PathParams(path=path))

        # Scroll & Wait
        case "scroll":
            direction = _require(rest, 1, "Usage: camoufox-cli scroll down [px]")
            amount = _require_int(rest[2], "scroll distance in pixels", 1) if len(rest) > 2 else 500
            return ScrollCommand(id="r1", params=ScrollParams(direction=direction, amount=amount))
        case "wait":
            target = _require(rest, 1, "Usage: camoufox-cli wait @e1 | camoufox-cli wait 2000 | camoufox-cli wait --url \"pattern\"")
            if target == "--url":
                pattern = _require(rest, 2, "Usage: camoufox-cli wait --url \"*/dashboard\"")
                return WaitCommand(id="r1", params=WaitParams(url=pattern))
            elif target.startswith("@"):
                return WaitCommand(id="r1", params=WaitParams(ref=target))
            elif target[0].isdigit():
                ms = _require_int(target, "wait duration in milliseconds", 1)
                return WaitCommand(id="r1", params=WaitParams(ms=ms))
            else:
                return WaitCommand(id="r1", params=WaitParams(selector=target))

        # Tab management
        case "tabs":
            return TabsCommand(id="r1")
        case "switch":
            index = _require(rest, 1, "Usage: camoufox-cli switch <tab-index>")
            return SwitchCommand(
                id="r1",
                params=SwitchParams(index=_require_int(index, "switch tab index")),
            )
        case "close-tab":
            return CloseTabCommand(id="r1")

        # Install
        case "install":
            return InstallCommand(id="r1", params=InstallParams(with_deps="--with-deps" in rest))

        # Session & Cookies
        case "sessions":
            return SessionsCommand(id="r1")
        case "cookies":
            if len(rest) > 1 and rest[1] == "import":
                path = _require(rest, 2, "Usage: camoufox-cli cookies import file.json")
                return CookiesCommand(id="r1", params=CookiesParams(op="import", path=path))
            elif len(rest) > 1 and rest[1] == "export":
                path = _require(rest, 2, "Usage: camoufox-cli cookies export file.json")
                return CookiesCommand(id="r1", params=CookiesParams(op="export", path=path))
            else:
                return CookiesCommand(id="r1", params=CookiesParams(op="list"))

        case _:
            print(f"Unknown command: {action}\n{USAGE}", file=sys.stderr)
            sys.exit(1)


def _require(args: list[str], idx: int, usage: str) -> str:
    if idx >= len(args):
        print(usage, file=sys.stderr)
        sys.exit(1)
    return args[idx]


def _require_int(value: str, label: str, minimum: int | None = None) -> int:
    try:
        n = int(value)
    except ValueError:
        print(f"Error: {label} must be an integer, got '{value}'", file=sys.stderr)
        sys.exit(1)
    if minimum is not None and n < minimum:
        print(f"Error: {label} must be >= {minimum}, got {n}", file=sys.stderr)
        sys.exit(1)
    return n


def print_response(response: Response, json_mode: bool) -> None:
    if json_mode:
        print(response.model_dump_json(indent=2, exclude_none=True))
        return

    if isinstance(response, ErrorResponse):
        print(f"Error: {response.error}", file=sys.stderr)
        sys.exit(1)

    if response.data is None:
        return

    data = response.data.model_dump(exclude_none=True)
    if not data:
        return

    tabs = data.get("tabs")

    if "snapshot" in data:
        print(data["snapshot"])
    elif "text" in data:
        print(data["text"])
    elif "result" in data:
        v = data["result"]
        print("null" if v is None else json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)
    elif data.get("closed"):
        pass  # silent
    elif "url" in data:
        if "title" in data:
            print(data["title"])
        print(data["url"])
    elif "title" in data:
        print(data["title"])
    elif tabs is None:
        print(json.dumps(data, indent=2, ensure_ascii=False))

    if tabs is not None:
        print(_format_tabs(tabs))


def _format_tabs(tabs: list[Tab]) -> str:
    if not tabs:
        return "(no tabs)"
    title_width = max(len(t.get("title") or "") for t in tabs)
    lines = []
    for t in tabs:
        marker = "*" if t.get("active") else " "
        title = (t.get("title") or "").ljust(title_width)
        lines.append(f"{marker} {t['index']}  {title}  {t['url']}")
    return "\n".join(lines)


_APT_DEPS = [
    "libxcb-shm0", "libx11-xcb1", "libx11-6", "libxcb1", "libxext6",
    "libxrandr2", "libxcomposite1", "libxcursor1", "libxdamage1", "libxfixes3",
    "libxi6", "libgtk-3-0", "libpangocairo-1.0-0", "libpango-1.0-0",
    "libatk1.0-0", "libcairo-gobject2", "libcairo2", "libgdk-pixbuf-2.0-0",
    "libxrender1", "libfreetype6", "libfontconfig1", "libdbus-1-3",
    "libnss3", "libnspr4", "libatk-bridge2.0-0", "libdrm2", "libxkbcommon0",
    "libatspi2.0-0", "libcups2", "libxshmfence1", "libgbm1",
]

_DNF_DEPS = [
    "nss", "nspr", "atk", "at-spi2-atk", "cups-libs", "libdrm",
    "libXcomposite", "libXdamage", "libXrandr", "mesa-libgbm", "pango",
    "alsa-lib", "libxkbcommon", "libxcb", "libX11-xcb", "libX11",
    "libXext", "libXcursor", "libXfixes", "libXi", "gtk3", "cairo-gobject",
]

_YUM_DEPS = [
    "nss", "nspr", "atk", "at-spi2-atk", "cups-libs", "libdrm",
    "libXcomposite", "libXdamage", "libXrandr", "mesa-libgbm", "pango",
    "alsa-lib", "libxkbcommon",
]


def _resolve_apt_libasound() -> str:
    """Newer Debian/Ubuntu renamed libasound2 to libasound2t64."""
    result = subprocess.run(
        ["dpkg", "-l", "libasound2t64"],
        capture_output=True,
    )
    return "libasound2t64" if result.returncode == 0 else "libasound2"


def _install_system_deps() -> None:
    import platform
    import shutil

    if platform.system() != "Linux":
        print("[camoufox-cli] System dependencies are only needed on Linux, skipping.", file=sys.stderr)
        return

    print("[camoufox-cli] Installing system dependencies...", file=sys.stderr)

    if shutil.which("apt-get"):
        deps = [*_APT_DEPS, _resolve_apt_libasound()]
        subprocess.run(["sudo", "apt-get", "update", "-y"], check=True)
        subprocess.run(["sudo", "apt-get", "install", "-y", *deps], check=True)
    elif shutil.which("dnf"):
        subprocess.run(["sudo", "dnf", "install", "-y", *_DNF_DEPS], check=True)
    elif shutil.which("yum"):
        subprocess.run(["sudo", "yum", "install", "-y", *_YUM_DEPS], check=True)
    else:
        print("[camoufox-cli] Could not detect a supported package manager (apt-get, dnf, yum).", file=sys.stderr)
        sys.exit(1)

    print("[camoufox-cli] System dependencies installed.", file=sys.stderr)


def main():
    args = sys.argv[1:]
    flags, command = parse_args(args)

    # Resolve default persistent path
    if flags.persistent == "":
        flags.persistent = os.path.expanduser(f"~/.camoufox-cli/profiles/{flags.session}")

    # Client-side: install
    if isinstance(command, InstallCommand):
        print("[camoufox-cli] Downloading browser...", file=sys.stderr)
        from camoufox.pkgman import CamoufoxFetcher
        fetcher = CamoufoxFetcher()
        fetcher.install()
        print("[camoufox-cli] Browser installed.", file=sys.stderr)
        if command.params.with_deps:
            _install_system_deps()
        return

    # Client-side: sessions
    if isinstance(command, SessionsCommand):
        sessions = list_sessions()
        if flags.json:
            print(json.dumps(sessions, indent=2))
        elif not sessions:
            print("No active sessions.")
        else:
            for s in sessions:
                print(s)
        return

    # Client-side: close --all
    if isinstance(command, CloseCommand) and command.params.all:
        sessions = list_sessions()
        if not sessions:
            print("No active sessions.")
            return
        close_cmd = CloseCommand(id="r1", params=CloseParams())
        for session in sessions:
            sock_path = get_socket_path(session)
            try:
                send_command(sock_path, close_cmd)
            except Exception as e:
                print(f"Failed to close session {session}: {e}", file=sys.stderr)
        return

    # Ensure daemon is running
    ensure_daemon(flags.session, flags.headed, flags.timeout, flags.persistent, flags.proxy, flags.geoip, flags.locale)

    sock_path = get_socket_path(flags.session)

    # Send command with retry
    last_err = ""
    for attempt in range(5):
        try:
            response = send_command(sock_path, command)
            print_response(response, flags.json)
            return
        except ResponseError as e:
            # Command was already delivered; the daemon may have executed it.
            # Retrying would re-run a possibly non-idempotent action.
            print(
                f"Error: command sent but reply failed ({e}); not retrying to "
                f"avoid re-running the action.",
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as e:
            last_err = str(e)
            if attempt < 4:
                time.sleep(0.2 * (attempt + 1))

    print(f"Error: Failed to connect to daemon after 5 attempts: {last_err}", file=sys.stderr)
    sys.exit(1)


USAGE = """\
Usage: camoufox-cli [flags] <command> [args]

Navigation:
  open <url>              Navigate to URL
  back                    Go back
  forward                 Go forward
  reload                  Reload page
  url                     Print current URL
  title                   Print page title
  close [--all]           Close browser and daemon (--all: all sessions)

Snapshot:
  snapshot [-i] [-s sel]  Aria tree (-i interactive, -s scoped)

Interaction:
  click @ref              Click element
  fill @ref "text"        Clear + type into input
  type @ref "text"        Type without clearing
  select @ref "option"    Select dropdown option
  check @ref              Toggle checkbox
  hover @ref              Hover over element
  press <key>             Press key (e.g. Enter, Control+a)

Data:
  text @ref|selector      Get text content
  eval "js expression"    Execute JavaScript
  screenshot [--full] [f] Screenshot to file or stdout
  pdf <file>              Save page as PDF

Scroll & Wait:
  scroll <dir> [px]       Scroll up/down (default 500px)
  wait <ms|@ref|--url p>  Wait for time/element/URL

Tabs:
  tabs                    List open tabs
  switch <index>          Switch to tab
  close-tab               Close current tab

Session:
  sessions                List active sessions
  cookies [import|export] Manage cookies

Setup:
  install [--with-deps]   Download browser (--with-deps: system libs)

Flags:
  --session <name>     Session name (default: "default")
  --headed             Show browser window
  --timeout <secs>     Daemon idle timeout (default: 1800)
  --json               Output as JSON
  --persistent [path]  Use persistent browser profile (default: ~/.camoufox-cli/profiles/<session>)
  --proxy <url>        Proxy server (e.g. http://host:port or https://host:443)
  --no-geoip           Disable automatic GeoIP spoofing (auto-enabled with --proxy)
  --locale <tag>       Force browser locale (e.g. "en-US" or "en-US,zh-CN")"""
