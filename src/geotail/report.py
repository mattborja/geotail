"""Static HTML report with a Leaflet world map and summary tables.

The report is opened in a browser, so pulling Leaflet from a CDN is fine —
the offline enrichment path never touches this module.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from geotail.stats import StatsCollector

_LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
_LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
_TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"


def write_report(path: str | Path, stats: StatsCollector, source: str, top_n: int = 10) -> None:
    """Render the collected stats to a standalone HTML file."""
    Path(path).write_text(_render(stats, source, top_n), encoding="utf-8")


def _rows(pairs: list[tuple[str, int]]) -> str:
    return "".join(
        f"<tr><td>{html.escape(name)}</td><td class='num'>{count:,}</td></tr>"
        for name, count in pairs
    )


def _render(stats: StatsCollector, source: str, top_n: int) -> str:
    markers = [
        {
            "ip": off.ip,
            "count": off.hits,
            "lat": off.enriched.latitude,
            "lon": off.enriched.longitude,
            "label": ", ".join(
                bit
                for bit in (off.enriched.city, off.enriched.country_name)
                if bit
            )
            or "unknown",
            "proxy": off.enriched.proxy_type if off.enriched.is_proxy else None,
        }
        for off in stats.all_records()
        if off.enriched.latitude is not None and off.enriched.longitude is not None
    ]
    offender_rows = "".join(
        "<tr><td>{ip}</td><td class='num'>{count:,}</td><td>{loc}</td>"
        "<td>{net}</td><td>{flag}</td></tr>".format(
            ip=html.escape(off.ip),
            count=off.hits,
            loc=html.escape(
                ", ".join(bit for bit in (off.enriched.city, off.enriched.country_name) if bit)
                or "unknown"
            ),
            net=html.escape(off.enriched.isp or off.enriched.asn or "—"),
            flag=(
                f"<span class='proxy'>⚠ {html.escape(off.enriched.proxy_type or 'PROXY')}</span>"
                if off.enriched.is_proxy
                else "✓"
            ),
        )
        for off in stats.top_offenders(top_n)
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>geotail report — {html.escape(source)}</title>
<link rel="stylesheet" href="{_LEAFLET_CSS}">
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0f1420; color: #e6e9ef; }}
h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.1rem; margin-top: 2rem; }}
a {{ color: #7aa2f7; }}
#map {{ height: 420px; border-radius: 8px; margin: 1rem 0; }}
table {{ border-collapse: collapse; min-width: 24rem; }}
td, th {{ padding: .35rem .8rem; border-bottom: 1px solid #2a3145; text-align: left; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.proxy {{ color: #f7768e; font-weight: 600; }}
.meta {{ color: #9aa5ce; }}
.grid {{ display: flex; gap: 3rem; flex-wrap: wrap; }}
</style>
</head>
<body>
<h1>geotail report</h1>
<p class="meta">source: {html.escape(source)} · events: {stats.total:,} ·
unique IPs: {stats.unique_ips:,} · suspicious: {stats.proxy_ratio:.1%}</p>
<div id="map"></div>
<div class="grid">
<div><h2>Top countries</h2><table>{_rows(stats.top_countries(top_n))}</table></div>
<div><h2>Top networks</h2><table>{_rows(stats.top_asns(top_n))}</table></div>
<div><h2>Proxy types</h2><table>{_rows(stats.proxy_types())}</table></div>
</div>
<h2>Top offenders</h2>
<table><tr><th>IP</th><th>Hits</th><th>Location</th><th>Network</th><th>Flags</th></tr>
{offender_rows}</table>
<p class="meta">geotail uses the IP2Location LITE database for
<a href="https://lite.ip2location.com">IP geolocation</a>.</p>
<script src="{_LEAFLET_JS}"></script>
<script>
const markers = {json.dumps(markers)};
const map = L.map('map').setView([20, 0], 2);
L.tileLayer('{_TILES}', {{ attribution: '&copy; OpenStreetMap contributors' }}).addTo(map);
for (const m of markers) {{
  const radius = 4 + Math.min(16, Math.log2(1 + m.count) * 3);
  L.circleMarker([m.lat, m.lon], {{
    radius, color: m.proxy ? '#f7768e' : '#7aa2f7', fillOpacity: 0.5, weight: 1,
  }}).bindPopup(`<b>${{m.ip}}</b><br>${{m.label}}<br>hits: ${{m.count}}` +
    (m.proxy ? `<br>proxy: ${{m.proxy}}` : '')).addTo(map);
}}
</script>
</body>
</html>
"""
