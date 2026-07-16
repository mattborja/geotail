"""Tests for geotail.tui: renderables carry the right text."""

from rich.console import Console

from geotail.models import EnrichedIP
from geotail.stats import StatsCollector
from geotail.tui import country_flag, render_dashboard


def render_to_text(stats: StatsCollector) -> str:
    console = Console(width=120, force_terminal=False, legacy_windows=False)
    with console.capture() as capture:
        console.print(render_dashboard(stats, "test.log", top_n=5))
    return capture.get()


def make_stats() -> StatsCollector:
    stats = StatsCollector()
    stats.add(
        EnrichedIP(
            ip="185.220.101.34",
            country_code="DE",
            country_name="Germany",
            city="Berlin",
            asn="AS60729",
            isp="Zwiebelfreunde e.V.",
            is_proxy=True,
            proxy_type="TOR",
        )
    )
    stats.add(
        EnrichedIP(
            ip="179.60.147.5",
            country_code="BR",
            country_name="Brazil",
            city="Sao Paulo",
            isp="Telefonica Brasil",
        )
    )
    return stats


def test_dashboard_shows_core_numbers() -> None:
    text = render_to_text(make_stats())
    assert "test.log" in text
    assert "50.0%" in text  # 1 of 2 events is a proxy
    assert "Germany" in text
    assert "Brazil" in text
    assert "185.220.101.34" in text
    assert "TOR" in text


def test_dashboard_renders_when_empty() -> None:
    text = render_to_text(StatsCollector())
    assert "geotail" in text
    assert "0.0%" in text


def test_dashboard_handles_all_none_record() -> None:
    stats = StatsCollector()
    stats.add(EnrichedIP(ip="10.0.0.1"))
    text = render_to_text(stats)
    assert "10.0.0.1" in text
    assert "unknown" in text


def test_country_flag() -> None:
    assert country_flag("US") == "\U0001f1fa\U0001f1f8"
    assert country_flag("de") == "\U0001f1e9\U0001f1ea"
    assert country_flag(None) == "\U0001f310"
    assert country_flag("USA") == "\U0001f310"
    assert country_flag("1A") == "\U0001f310"
