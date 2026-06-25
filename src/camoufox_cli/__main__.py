"""Entry point: python -m camoufox_cli"""

import argparse
import sys

from .server import DaemonServer


class _Args(argparse.Namespace):
    """Typed view of the daemon's parsed CLI args.

    Defaults mirror the ``add_argument`` defaults below; argparse overwrites
    them from the command line.
    """

    session: str = "default"
    headless: bool = True
    headed: bool = False
    timeout: int = 1800
    persistent: str | None = None
    proxy: str | None = None
    geoip: bool = True
    locale: str | None = None
    clone_from: str | None = None


def main():
    parser = argparse.ArgumentParser(description="camoufox-cli daemon server")
    _ = parser.add_argument("--session", default="default", help="Session name")
    _ = parser.add_argument(
        "--headless", action="store_true", default=True, help="Run headless (default)"
    )
    _ = parser.add_argument("--headed", action="store_true", help="Show browser window")
    _ = parser.add_argument(
        "--timeout", type=int, default=1800, help="Idle timeout in seconds"
    )
    _ = parser.add_argument(
        "--persistent", default=None, help="Path for persistent browser profile"
    )
    _ = parser.add_argument("--proxy", default=None, help="Proxy server URL")
    _ = parser.add_argument(
        "--no-geoip",
        dest="geoip",
        action="store_false",
        default=True,
        help="Disable automatic GeoIP spoofing when using a proxy",
    )
    _ = parser.add_argument(
        "--locale",
        default=None,
        help="Force browser locale (e.g. 'en-US' or 'en-US,zh-CN')",
    )
    _ = parser.add_argument(
        "--clone-from",
        default=None,
        help="Seed an ephemeral profile copied from this persistent profile path",
    )
    args = parser.parse_args(namespace=_Args())

    headless = not args.headed

    server = DaemonServer(
        session=args.session,
        headless=headless,
        timeout=args.timeout,
        persistent=args.persistent,
        proxy=args.proxy,
        geoip=args.geoip,
        locale=args.locale,
        clone_from=args.clone_from,
    )

    print(
        f"[camoufox-cli] Starting daemon session={args.session} headless={headless}",
        file=sys.stderr,
    )
    server.start()


if __name__ == "__main__":
    main()
