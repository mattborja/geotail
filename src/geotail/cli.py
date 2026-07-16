"""Command-line entry point: argument parsing and wiring."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from collections.abc import Iterator
from importlib import resources
from pathlib import Path

from rich.console import Console
from rich.live import Live

import geotail
from geotail.engine import Enricher
from geotail.parsers import get_parser
from geotail.providers.base import GeoProvider, ProxyProvider
from geotail.providers.fake import demo_providers
from geotail.report import write_report
from geotail.stats import StatsCollector
from geotail.tui import render_dashboard

LITE_URL = "https://lite.ip2location.com"
GEO_DB_ENV = "IP2LOCATION_DB"
PROXY_DB_ENV = "IP2PROXY_DB"
DEFAULT_DATA_DIR = Path("data")
GEO_DB_HINT = "IP2LOCATION-LITE-DB11.BIN"
PROXY_DB_HINT = "IP2PROXY-LITE-PX11.BIN"

MISSING_DB_MESSAGE = f"""geotail: no IP2Location database found.

geotail enriches IPs offline from free IP2Location LITE BIN files.
Grab them (free account, no credit card) from {LITE_URL} :

  1. {GEO_DB_HINT}   (geolocation — required)
  2. {PROXY_DB_HINT}  (proxy/VPN/Tor — optional but recommended)

then either drop them into ./{DEFAULT_DATA_DIR}/ or point geotail at them:

  geotail --geo-db /path/to/{GEO_DB_HINT} --proxy-db /path/to/{PROXY_DB_HINT}
  export {GEO_DB_ENV}=/path/to/{GEO_DB_HINT}

No databases handy? Try the built-in demo:  geotail --demo
"""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geotail",
        description=(
            "Read server logs, enrich every source IP offline with IP2Location "
            "geolocation and proxy data, and render a live terminal dashboard."
        ),
        epilog=geotail.ATTRIBUTION,
    )
    parser.add_argument(
        "source",
        nargs="?",
        metavar="SOURCE",
        help="log file to read (same as --file); omit to read stdin",
    )
    parser.add_argument("--file", dest="file", metavar="PATH", help="read from a file")
    parser.add_argument(
        "--format",
        choices=["auto", "nginx", "apache", "sshd", "generic"],
        default="auto",
        help="log format (default: auto)",
    )
    parser.add_argument(
        "--regex", metavar="PATTERN", help="custom IP-extraction regex (implies generic)"
    )
    parser.add_argument("--geo-db", metavar="PATH", help="IP2Location BIN file")
    parser.add_argument("--proxy-db", metavar="PATH", help="IP2Proxy BIN file (optional)")
    parser.add_argument(
        "--json", action="store_true", help="emit enriched JSONL to stdout instead of the TUI"
    )
    parser.add_argument(
        "--tui", action="store_true", help="force the live dashboard even when piped"
    )
    parser.add_argument("--report", metavar="PATH", help="write a static HTML report on exit")
    parser.add_argument(
        "--follow", action="store_true", help="keep reading as the file grows (tail -f)"
    )
    parser.add_argument(
        "--top", type=int, default=10, metavar="N", help="rows in top-N panels (default 10)"
    )
    parser.add_argument(
        "--demo", action="store_true", help="run against bundled fake data, no BIN needed"
    )
    parser.add_argument(
        "--about", action="store_true", help="print version and IP2Location attribution"
    )
    return parser


def resolve_db_path(cli_value: str | None, env_var: str, patterns: tuple[str, ...]) -> Path | None:
    """Resolve a BIN path: CLI flag > environment variable > ./data/ scan."""
    if cli_value:
        return Path(cli_value)
    env_value = os.environ.get(env_var)
    if env_value:
        return Path(env_value)
    if DEFAULT_DATA_DIR.is_dir():
        for entry in sorted(DEFAULT_DATA_DIR.iterdir()):
            name = entry.name.upper()
            if entry.is_file() and any(
                name.startswith(prefix) and name.endswith(".BIN") for prefix in patterns
            ):
                return entry
    return None


def build_providers(
    args: argparse.Namespace,
) -> tuple[GeoProvider, ProxyProvider | None] | None:
    """Build the provider pair, or ``None`` after printing a friendly error."""
    if args.demo:
        geo, proxy = demo_providers()
        return geo, proxy

    geo_path = resolve_db_path(args.geo_db, GEO_DB_ENV, ("IP2LOCATION",))
    proxy_path = resolve_db_path(args.proxy_db, PROXY_DB_ENV, ("IP2PROXY",))

    if geo_path is None:
        print(MISSING_DB_MESSAGE, file=sys.stderr)
        return None
    if not geo_path.is_file():
        print(f"geotail: geolocation database not found: {geo_path}", file=sys.stderr)
        print(MISSING_DB_MESSAGE, file=sys.stderr)
        return None

    # Import lazily so --demo and --about never touch the BIN-backed code path.
    from geotail.providers.ip2location import IP2LocationGeoProvider, IP2ProxyProvider

    try:
        geo_provider: GeoProvider = IP2LocationGeoProvider(geo_path)
    except Exception as exc:
        print(f"geotail: could not open geolocation database {geo_path}: {exc}", file=sys.stderr)
        return None

    proxy_provider: ProxyProvider | None = None
    if proxy_path is not None:
        if not proxy_path.is_file():
            print(
                f"geotail: proxy database not found: {proxy_path} — continuing without it",
                file=sys.stderr,
            )
        else:
            try:
                proxy_provider = IP2ProxyProvider(proxy_path)
            except Exception as exc:
                print(
                    f"geotail: could not open proxy database {proxy_path}: {exc}"
                    " — continuing without it",
                    file=sys.stderr,
                )
    return geo_provider, proxy_provider


def iter_file(path: Path, follow: bool) -> Iterator[str]:
    """Yield lines from a file; with ``follow``, keep polling as it grows."""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            line = handle.readline()
            if line:
                yield line
                continue
            if not follow:
                return
            # At EOF: handle truncation (e.g. logrotate), else poll.
            try:
                if path.stat().st_size < handle.tell():
                    handle.seek(0)
            except OSError:
                pass
            time.sleep(0.25)


def iter_demo_lines(streaming: bool) -> Iterator[str]:
    """Replay the bundled demo log; loop with a delay when streaming (TUI)."""
    text = resources.files("geotail").joinpath("demo.log").read_text(encoding="utf-8")
    lines = text.splitlines()
    while True:
        for line in lines:
            yield line
            if streaming:
                time.sleep(0.08)
        if not streaming:
            return


def _emit_jsonl(record_dict: dict[str, object]) -> None:
    print(json.dumps(record_dict, ensure_ascii=False), flush=True)


def run_stream(
    lines: Iterator[str],
    enricher: Enricher,
    args: argparse.Namespace,
    source_name: str,
    use_tui: bool,
) -> StatsCollector:
    """Drive the parse -> enrich -> aggregate loop in JSONL or TUI mode."""
    parse = get_parser(args.format, args.regex)
    stats = StatsCollector()
    console = Console()

    def consume(on_event: bool) -> None:
        for line in lines:
            parsed = parse(line.rstrip("\n"))
            if parsed is None:
                if line.strip():
                    stats.parse_failures += 1
                continue
            record = enricher.enrich(parsed.ip)
            stats.add(record)
            if on_event:
                payload = record.to_dict()
                payload["ts"] = (
                    parsed.timestamp.isoformat() if parsed.timestamp is not None else None
                )
                _emit_jsonl(payload)
            else:
                live.update(render_dashboard(stats, source_name, args.top))

    try:
        if use_tui:
            with Live(
                render_dashboard(stats, source_name, args.top),
                console=console,
                refresh_per_second=8,
            ) as live:
                consume(on_event=False)
        else:
            consume(on_event=True)
    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        # Downstream pipe closed (e.g. `geotail --json | head`); exit quietly.
        with contextlib.suppress(OSError):
            sys.stdout.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.about:
        print(f"geotail {geotail.__version__}")
        print(geotail.ATTRIBUTION)
        return 0

    if args.json and args.tui:
        print("geotail: --json and --tui are mutually exclusive", file=sys.stderr)
        return 2
    if args.source and args.file:
        print("geotail: give either a positional SOURCE or --file, not both", file=sys.stderr)
        return 2
    if args.top < 1:
        print("geotail: --top must be at least 1", file=sys.stderr)
        return 2

    providers = build_providers(args)
    if providers is None:
        return 2
    geo_provider, proxy_provider = providers
    enricher = Enricher(geo_provider, proxy_provider)

    use_tui = args.tui or (not args.json and sys.stdout.isatty())

    file_arg = args.file or args.source
    if file_arg is not None:
        path = Path(file_arg)
        if not path.is_file():
            print(f"geotail: file not found: {path}", file=sys.stderr)
            return 2
        lines: Iterator[str] = iter_file(path, follow=args.follow)
        source_name = str(path)
    elif args.demo and sys.stdin.isatty():
        lines = iter_demo_lines(streaming=use_tui)
        source_name = "demo stream"
    else:
        if args.follow:
            print("geotail: --follow requires --file", file=sys.stderr)
            return 2
        lines = iter(sys.stdin)
        source_name = "stdin"

    stats = run_stream(lines, enricher, args, source_name, use_tui)

    if args.report:
        try:
            write_report(args.report, stats, source_name, args.top)
            print(f"geotail: report written to {args.report}", file=sys.stderr)
        except OSError as exc:
            print(f"geotail: could not write report: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
