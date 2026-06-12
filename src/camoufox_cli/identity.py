"""Persistent identity: freeze fingerprint/OS into a persistent dir.

When a user launches with ``--persistent <dir>``, a ``camoufox-cli.json`` file
is written on first launch capturing the generated fingerprint, OS, locale,
and derived timezone/geolocation. Subsequent launches reload it so the browser
reports the same device identity to every site.

Fingerprint/OS/canvas+font seeds are frozen for the lifetime of the identity.
User-controllable fields (locale; proxy-derived timezone/geolocation) are
updated to match the command line whenever it's explicitly passed — so the
stored identity always reflects the most recent intent.
"""

from __future__ import annotations

import dataclasses
import datetime
import random
import sys
from collections.abc import Mapping
from pathlib import Path

from .models import IDENTITY_FILENAME, Config, Geo, Identity


def _host_os() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _identity_path(persistent_dir: str) -> Path:
    return Path(persistent_dir) / IDENTITY_FILENAME


def _write(path: Path, identity: Identity) -> None:
    _ = path.write_text(
        identity.model_dump_json(by_alias=True, exclude_none=True, indent=2)
    )


def load_or_create(
    persistent_dir: str,
    locale: str | None,
    proxy: str | None,
    geoip: bool,
) -> Identity:
    """Return the identity for this persistent directory.

    On first launch, a fresh identity is generated and written:
      - fingerprint: browserforge, firefox, host OS
      - canvas/font seeds: random, stored so future launches reproduce them
      - timezone/geolocation: derived via GeoIP if proxy is set and geoip=True
      - locale: recorded if passed on this first launch, else null

    On subsequent launches, ``<persistent_dir>/camoufox-cli.json`` is loaded.
    Fields the user explicitly passes on the command line overwrite the
    stored values (``--locale``; ``--proxy`` + geoip re-derives timezone /
    geolocation). Fingerprint, OS, and canvas/font seeds are never touched
    after first launch.
    """
    path = _identity_path(persistent_dir)
    if path.exists():
        identity = Identity.model_validate_json(path.read_text())
        if _apply_cli_overrides(identity, locale, proxy, geoip):
            _write(path, identity)
        return identity

    from browserforge.fingerprints import Fingerprint, FingerprintGenerator

    os_ = _host_os()
    generator: FingerprintGenerator = FingerprintGenerator(browser="firefox", os=os_)
    # browserforge's generate() ends in an untyped **header_kwargs, so pyright
    # treats the method type as partially unknown (return is still Fingerprint).
    fp: Fingerprint = generator.generate()  # pyright: ignore[reportUnknownMemberType]

    config = Config(
        canvas_aa_offset=random.randint(-50, 50),
        canvas_aa_cap_offset=bool(random.randint(0, 1)),
        fonts_spacing_seed=random.randint(0, 2**32 - 1),
    )

    if proxy and geoip:
        _ = _merge_geo(config, _geolocate_proxy(proxy))

    identity = Identity(
        created_at=datetime.datetime.now(datetime.UTC).isoformat(),
        os=os_,
        locale=locale,
        fingerprint=dataclasses.asdict(fp),
        config=config,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, identity)
    return identity


def _apply_cli_overrides(
    identity: Identity,
    locale: str | None,
    proxy: str | None,
    geoip: bool,
) -> bool:
    """Mutate identity with CLI-passed values. Return True if anything changed."""
    changed = False

    if locale is not None and identity.locale != locale:
        identity.locale = locale
        changed = True

    if proxy and geoip:
        derived = _geolocate_proxy(proxy)
        if derived and _merge_geo(identity.config, derived):
            changed = True

    return changed


def _merge_geo(config: Config, derived: Geo | None) -> bool:
    """Merge proxy-derived geo into config. Return True if anything changed."""
    if not derived:
        return False
    changed = False
    if derived.timezone and config.timezone != derived.timezone:
        config.timezone = derived.timezone
        changed = True
    if config.geolocation_latitude != derived.latitude:
        config.geolocation_latitude = derived.latitude
        changed = True
    if config.geolocation_longitude != derived.longitude:
        config.geolocation_longitude = derived.longitude
        changed = True
    if derived.accuracy is not None and config.geolocation_accuracy != derived.accuracy:
        config.geolocation_accuracy = derived.accuracy
        changed = True
    return changed


def to_launch_kwargs(identity: Identity) -> dict[str, object]:
    """Translate identity into kwargs for Camoufox(**kwargs).

    Returns fingerprint/os/config (always) and locale (when set). Does NOT
    set persistent_context/user_data_dir — the caller handles those.
    """
    from browserforge.fingerprints import Fingerprint

    fp = _rebuild_dataclass(Fingerprint, identity.fingerprint)
    kwargs: dict[str, object] = {
        "fingerprint": fp,
        "os": identity.os,
        "config": identity.config.model_dump(by_alias=True, exclude_none=True),
    }

    if identity.locale:
        parts = [s.strip() for s in identity.locale.split(",") if s.strip()]
        if parts:
            kwargs["locale"] = parts if len(parts) > 1 else parts[0]

    return kwargs


def _rebuild_dataclass(cls: object, value: object) -> object:
    """Reconstruct a nested dataclass tree from a plain dict."""
    if value is None:
        return None
    if (
        isinstance(cls, type)
        and dataclasses.is_dataclass(cls)
        and isinstance(value, Mapping)
    ):
        kwargs: dict[str, object] = {}
        for f in dataclasses.fields(cls):
            field_type: object = f.type
            # value is an opaque Mapping (browserforge asdict output, no element
            # types), so .get() is partially unknown — reconstruction is reflective.
            field_value: object = value.get(f.name)  # pyright: ignore[reportUnknownMemberType]
            kwargs[f.name] = _rebuild_dataclass(field_type, field_value)
        return cls(**kwargs)
    return value


def _geolocate_proxy(proxy_url: str) -> Geo | None:
    """Return the proxy's public-IP geolocation, or None if anything fails."""
    try:
        from camoufox.ip import public_ip, valid_ipv4, valid_ipv6
        from camoufox.locale import get_geolocation
    except Exception:
        return None

    try:
        ip = public_ip(_proxy_url_with_auth(proxy_url))
        if not (valid_ipv4(ip) or valid_ipv6(ip)):
            return None
        geo = get_geolocation(ip)
        return Geo(
            timezone=geo.timezone,
            latitude=geo.latitude,
            longitude=geo.longitude,
            accuracy=geo.accuracy if geo.accuracy else None,
        )
    except Exception:
        return None


def _proxy_url_with_auth(proxy_url: str) -> str:
    """Rebuild proxy URL as scheme://user:pass@host:port for public_ip()."""
    from urllib.parse import quote, urlparse

    from .proxy import parse_proxy_settings

    settings = parse_proxy_settings(proxy_url)
    parsed = urlparse(settings["server"])
    if "username" in settings:
        user = quote(settings["username"], safe="")
        password = quote(settings.get("password", ""), safe="")
        return f"{parsed.scheme}://{user}:{password}@{parsed.netloc}"
    return settings["server"]
