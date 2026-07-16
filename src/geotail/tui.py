"""Live terminal dashboard rendered with rich."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from geotail.stats import StatsCollector

_PROXY_STYLES = {
    "TOR": "bold red",
    "VPN": "bold magenta",
    "DCH": "yellow",
    "PUB": "bold yellow",
    "WEB": "yellow",
    "RES": "red",
    "SES": "yellow",
    "AIC": "yellow",
}

_COUNTRY_FLAG_OFFSET = 0x1F1E6 - ord("A")


def country_flag(country_code: str | None) -> str:
    """Regional-indicator emoji for a 2-letter country code, or a globe."""
    if country_code is None or len(country_code) != 2 or not country_code.isalpha():
        return "\U0001f310"
    return "".join(chr(ord(ch) + _COUNTRY_FLAG_OFFSET) for ch in country_code.upper())


def render_header(stats: StatsCollector, source: str) -> Panel:
    ratio = stats.proxy_ratio
    ratio_style = "green" if ratio < 0.1 else "yellow" if ratio < 0.3 else "bold red"
    line = Text.assemble(
        ("source ", "dim"),
        (source, "bold cyan"),
        ("   events ", "dim"),
        (f"{stats.total:,}", "bold"),
        ("   unique IPs ", "dim"),
        (f"{stats.unique_ips:,}", "bold"),
        ("   suspicious ", "dim"),
        (f"{ratio:.1%}", ratio_style),
        ("   skipped ", "dim"),
        (f"{stats.parse_failures:,}", "dim"),
    )
    return Panel(line, title="[bold]geotail[/bold] — offline IP intelligence", border_style="cyan")


def render_countries(stats: StatsCollector, top_n: int) -> Panel:
    table = Table(box=None, expand=True, pad_edge=False)
    table.add_column("Country", overflow="ellipsis", no_wrap=True)
    table.add_column("Hits", justify="right", style="bold")
    table.add_column("", ratio=1)
    rows = stats.top_countries(top_n)
    peak = rows[0][1] if rows else 1
    for name, count in rows:
        bar = "█" * max(1, round(count / peak * 20))
        table.add_row(name, f"{count:,}", Text(bar, style="cyan"))
    return Panel(table, title="Top countries", border_style="blue")


def render_asns(stats: StatsCollector, top_n: int) -> Panel:
    table = Table(box=None, expand=True, pad_edge=False)
    table.add_column("ASN / ISP", overflow="ellipsis", no_wrap=True, ratio=1)
    table.add_column("Hits", justify="right", style="bold")
    for label, count in stats.top_asns(top_n):
        table.add_row(label, f"{count:,}")
    return Panel(table, title="Top networks", border_style="blue")


def render_offenders(stats: StatsCollector, top_n: int) -> Panel:
    table = Table(expand=True, header_style="bold", box=None)
    table.add_column("IP", no_wrap=True)
    table.add_column("Hits", justify="right")
    table.add_column("Location", overflow="ellipsis", no_wrap=True, ratio=1)
    table.add_column("Network", overflow="ellipsis", no_wrap=True, ratio=1)
    table.add_column("Flags", no_wrap=True)
    for ip, count, rec in stats.top_offenders(top_n):
        location_bits = [bit for bit in (rec.city, rec.country_name) if bit]
        location = f"{country_flag(rec.country_code)} " + (
            ", ".join(location_bits) if location_bits else "unknown"
        )
        network = rec.isp or rec.asn or "—"
        if rec.is_proxy:
            tag = rec.proxy_type or "PROXY"
            flags = Text(f"⚠ {tag}", style=_PROXY_STYLES.get(tag, "bold red"))
        else:
            flags = Text("✓", style="green")
        ip_style = "bold red" if rec.is_proxy else "bold"
        table.add_row(Text(ip, style=ip_style), f"{count:,}", location, network, flags)
    return Panel(table, title="Top offenders", border_style="blue")


def render_dashboard(stats: StatsCollector, source: str, top_n: int = 10) -> RenderableType:
    """Compose the full dashboard renderable for one refresh."""
    columns = Table.grid(expand=True)
    columns.add_column(ratio=1)
    columns.add_column(ratio=1)
    columns.add_row(render_countries(stats, top_n), render_asns(stats, top_n))
    return Group(render_header(stats, source), columns, render_offenders(stats, top_n))
