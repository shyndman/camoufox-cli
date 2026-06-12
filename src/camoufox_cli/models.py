"""Pydantic models for every trust boundary in the app.

Two domains live here because both parse data that originates outside the
process and both need validation:

* **Wire protocol** — ``Command`` / ``Response`` flow as JSON lines over the
  unix socket between CLI and daemon. ``Command`` is a discriminated union on
  ``action`` so a malformed or unknown command fails at the parse, not deep
  inside a handler.
* **Identity** — ``Identity`` / ``Config`` are persisted to ``camoufox-cli.json``
  and reloaded on later launches. ``Config`` uses field aliases because its
  Camoufox-facing keys contain colons (``canvas:aaOffset``), which are not valid
  Python identifiers. Dump with ``by_alias=True, exclude_none=True`` to get the
  exact dict Camoufox expects.

In-process-only shapes (``Tab``, ``Flags``, ``ProxySettings``) are not here —
see ``types.py``.
"""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

# ===========================================================================
# Wire protocol — commands
# ===========================================================================
#
# Each command is ``{id, action, params}``. Per-action param models forbid
# extra keys so CLI/daemon drift surfaces immediately. ``id`` is the
# request id echoed back on the response.


class _Params(BaseModel):
    """Base for command params: reject unknown keys to catch drift."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class _NoParams(_Params):
    """Commands that take no parameters."""


class _Command(BaseModel):
    """Base wire command envelope."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    id: str


# --- Navigation ------------------------------------------------------------


class OpenParams(_Params):
    url: str
    # Injected by the daemon from its launch preference if absent.
    headless: bool = True


class OpenCommand(_Command):
    action: Literal["open"] = "open"
    params: OpenParams


class BackCommand(_Command):
    action: Literal["back"] = "back"
    params: _NoParams = _NoParams()


class ForwardCommand(_Command):
    action: Literal["forward"] = "forward"
    params: _NoParams = _NoParams()


class ReloadCommand(_Command):
    action: Literal["reload"] = "reload"
    params: _NoParams = _NoParams()


class UrlCommand(_Command):
    action: Literal["url"] = "url"
    params: _NoParams = _NoParams()


class TitleCommand(_Command):
    action: Literal["title"] = "title"
    params: _NoParams = _NoParams()


class CloseParams(_Params):
    all: bool = False


class CloseCommand(_Command):
    action: Literal["close"] = "close"
    params: CloseParams = CloseParams()


# --- Snapshot --------------------------------------------------------------


class SnapshotParams(_Params):
    interactive: bool = False
    selector: str | None = None


class SnapshotCommand(_Command):
    action: Literal["snapshot"] = "snapshot"
    params: SnapshotParams = SnapshotParams()


# --- Interaction -----------------------------------------------------------


class RefParams(_Params):
    ref: str


class ClickCommand(_Command):
    action: Literal["click"] = "click"
    params: RefParams


class CheckCommand(_Command):
    action: Literal["check"] = "check"
    params: RefParams


class HoverCommand(_Command):
    action: Literal["hover"] = "hover"
    params: RefParams


class RefTextParams(_Params):
    ref: str
    text: str


class FillCommand(_Command):
    action: Literal["fill"] = "fill"
    params: RefTextParams


class TypeCommand(_Command):
    action: Literal["type"] = "type"
    params: RefTextParams


class SelectParams(_Params):
    ref: str
    value: str


class SelectCommand(_Command):
    action: Literal["select"] = "select"
    params: SelectParams


class PressParams(_Params):
    key: str


class PressCommand(_Command):
    action: Literal["press"] = "press"
    params: PressParams


# --- Data extraction -------------------------------------------------------


class TextParams(_Params):
    target: str


class TextCommand(_Command):
    action: Literal["text"] = "text"
    params: TextParams


class EvalParams(_Params):
    expression: str


class EvalCommand(_Command):
    action: Literal["eval"] = "eval"
    params: EvalParams


class ScreenshotParams(_Params):
    path: str | None = None
    full_page: bool = False


class ScreenshotCommand(_Command):
    action: Literal["screenshot"] = "screenshot"
    params: ScreenshotParams = ScreenshotParams()


class PathParams(_Params):
    path: str


class PdfCommand(_Command):
    action: Literal["pdf"] = "pdf"
    params: PathParams


# --- Scroll & wait ---------------------------------------------------------


class ScrollParams(_Params):
    direction: str = "down"
    amount: int = 500


class ScrollCommand(_Command):
    action: Literal["scroll"] = "scroll"
    params: ScrollParams


class WaitParams(_Params):
    # Exactly one of these is set by the CLI; the handler checks in order.
    ms: int | None = None
    ref: str | None = None
    selector: str | None = None
    url: str | None = None


class WaitCommand(_Command):
    action: Literal["wait"] = "wait"
    params: WaitParams


# --- Tab management --------------------------------------------------------


class TabsCommand(_Command):
    action: Literal["tabs"] = "tabs"
    params: _NoParams = _NoParams()


class SwitchParams(_Params):
    index: int


class SwitchCommand(_Command):
    action: Literal["switch"] = "switch"
    params: SwitchParams


class CloseTabCommand(_Command):
    action: Literal["close-tab"] = "close-tab"
    params: _NoParams = _NoParams()


# --- Install / sessions (handled CLI-side, never reach the daemon) ---------


class InstallParams(_Params):
    with_deps: bool = False


class InstallCommand(_Command):
    action: Literal["install"] = "install"
    params: InstallParams = InstallParams()


class SessionsCommand(_Command):
    action: Literal["sessions"] = "sessions"
    params: _NoParams = _NoParams()


# --- Cookies ---------------------------------------------------------------


class CookiesParams(_Params):
    op: Literal["list", "export", "import"] = "list"
    path: str | None = None


class CookiesCommand(_Command):
    action: Literal["cookies"] = "cookies"
    params: CookiesParams = CookiesParams()


# --- The discriminated union ----------------------------------------------

Command = Annotated[
    OpenCommand
    | BackCommand
    | ForwardCommand
    | ReloadCommand
    | UrlCommand
    | TitleCommand
    | CloseCommand
    | SnapshotCommand
    | ClickCommand
    | FillCommand
    | TypeCommand
    | SelectCommand
    | CheckCommand
    | HoverCommand
    | PressCommand
    | TextCommand
    | EvalCommand
    | ScreenshotCommand
    | PdfCommand
    | ScrollCommand
    | WaitCommand
    | TabsCommand
    | SwitchCommand
    | CloseTabCommand
    | InstallCommand
    | SessionsCommand
    | CookiesCommand,
    Field(discriminator="action"),
]

command_adapter: TypeAdapter[Command] = TypeAdapter(Command)


# ===========================================================================
# Wire protocol — responses
# ===========================================================================


class ResponseData(BaseModel):
    """The ``data`` payload of an ok response.

    Every key is optional — each command fills only the subset it produces.
    ``extra="allow"`` keeps round-trip fidelity for free-form payloads
    (``eval`` results, raw cookie dicts) without enumerating them.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    url: str | None = None
    title: str | None = None
    snapshot: str | None = None
    text: str | None = None
    result: JsonValue = None
    path: str | None = None
    base64: str | None = None
    closed: bool | None = None
    count: int | None = None
    tabs: list["Tab"] | None = None
    cookies: list[dict[str, JsonValue]] | None = None


class OkResponse(BaseModel):
    id: str
    success: Literal[True] = True
    data: ResponseData | None = None


class ErrorResponse(BaseModel):
    id: str
    success: Literal[False] = False
    error: str


Response = Annotated[
    OkResponse | ErrorResponse,
    Field(discriminator="success"),
]

response_adapter: TypeAdapter[Response] = TypeAdapter(Response)


# ===========================================================================
# Identity (persisted to camoufox-cli.json)
# ===========================================================================

IDENTITY_FILENAME = "camoufox-cli.json"
IDENTITY_VERSION = 1


class Geo(BaseModel):
    """Proxy-derived geolocation. Feeds ``Config`` via ``_merge_geo``."""

    timezone: str
    latitude: float
    longitude: float
    accuracy: float | None = None


class Config(BaseModel):
    """Camoufox ``config`` kwarg, also persisted inside the identity file.

    Field names are Python-legal; the colon-bearing wire keys are aliases.
    ``populate_by_name=True`` lets us construct with either; ``extra="allow"``
    preserves any Camoufox config keys we don't model. Serialize for Camoufox /
    disk with ``model_dump(by_alias=True, exclude_none=True)``.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True, extra="allow")

    canvas_aa_offset: int | None = Field(default=None, validation_alias="canvas:aaOffset", serialization_alias="canvas:aaOffset")
    canvas_aa_cap_offset: bool | None = Field(default=None, validation_alias="canvas:aaCapOffset", serialization_alias="canvas:aaCapOffset")
    fonts_spacing_seed: int | None = Field(default=None, validation_alias="fonts:spacing_seed", serialization_alias="fonts:spacing_seed")
    timezone: str | None = None
    geolocation_latitude: float | None = Field(default=None, validation_alias="geolocation:latitude", serialization_alias="geolocation:latitude")
    geolocation_longitude: float | None = Field(default=None, validation_alias="geolocation:longitude", serialization_alias="geolocation:longitude")
    geolocation_accuracy: float | None = Field(default=None, validation_alias="geolocation:accuracy", serialization_alias="geolocation:accuracy")


class Identity(BaseModel):
    """Frozen device identity for a ``--persistent`` directory."""

    version: int = IDENTITY_VERSION
    created_at: str
    os: str
    locale: str | None = None
    # browserforge Fingerprint as a plain dict (dataclasses.asdict). Opaque to
    # us — we only round-trip it back through identity._rebuild_dataclass.
    fingerprint: dict[str, JsonValue]
    config: Config = Field(default_factory=Config)


# Resolve the forward ref to the TypedDict in types.py.
from .types import Tab  # noqa: E402  (deferred to avoid a cycle at import time)

_ = ResponseData.model_rebuild()
