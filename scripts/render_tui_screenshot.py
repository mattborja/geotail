#!/usr/bin/env python3
"""Render the geotail TUI dashboard to a static SVG screenshot for the README.

Drives the same parse -> enrich -> aggregate pipeline the CLI uses, then
exports the final rich renderable via Console(record=True).save_svg() — so
these screenshots are real tool output, not mockups.

Usage:
    scripts/render_tui_screenshot.py LOG_FILE OUT.svg "title shown in the terminal chrome" [--real]

    --real   use the BIN files in ./data/ instead of the --demo fake provider
             (requires IP2LOCATION-LITE-DB11.BIN / IP2PROXY-LITE-PX11.BIN present)

Example:
    scripts/render_tui_screenshot.py sample.log docs/img/tui-demo.svg \\
        "geotail --demo --file sample.log --tui"
"""

from __future__ import annotations

import sys

from rich.console import Console

from geotail.engine import Enricher
from geotail.parsers import get_parser
from geotail.providers.fake import demo_providers
from geotail.stats import StatsCollector
from geotail.tui import render_dashboard


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    log_file, out_svg, title = sys.argv[1], sys.argv[2], sys.argv[3]
    use_real = "--real" in sys.argv[4:]

    if use_real:
        from geotail.providers.ip2location import IP2LocationGeoProvider, IP2ProxyProvider

        geo = IP2LocationGeoProvider("data/IP2LOCATION-LITE-DB11.BIN")
        proxy = IP2ProxyProvider("data/IP2PROXY-LITE-PX11.BIN")
    else:
        geo, proxy = demo_providers()

    enricher = Enricher(geo, proxy)
    parse = get_parser("auto", None)
    stats = StatsCollector()

    with open(log_file, encoding="utf-8", errors="replace") as f:
        for line in f:
            parsed = parse(line.rstrip("\n"))
            if parsed is None:
                if line.strip():
                    stats.parse_failures += 1
                continue
            stats.add(enricher.enrich(parsed.ip))

    console = Console(record=True, width=104, height=30)
    console.print(render_dashboard(stats, log_file, 8))
    console.save_svg(out_svg, title=title)
    print(f"wrote {out_svg} ({stats.total} events, {stats.unique_ips} unique IPs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
