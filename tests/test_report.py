"""Tests for geotail.report."""

from pathlib import Path

from geotail.models import EnrichedIP
from geotail.report import write_report
from geotail.stats import StatsCollector


def make_stats() -> StatsCollector:
    stats = StatsCollector()
    stats.add(
        EnrichedIP(
            ip="8.8.8.8",
            country_code="US",
            country_name="United States of America",
            city="Mountain View",
            latitude=37.4,
            longitude=-122.1,
            isp="Google LLC",
            asn="AS15169",
            is_proxy=True,
            proxy_type="DCH",
        )
    )
    stats.add(EnrichedIP(ip="203.0.113.5", country_name="<Unknownland>"))
    return stats


def test_report_contains_summary_and_markers(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    write_report(out, make_stats(), "sample.log")
    html_text = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_text
    assert "sample.log" in html_text
    assert "8.8.8.8" in html_text
    assert "United States of America" in html_text
    assert "leaflet" in html_text
    assert '"lat": 37.4' in html_text
    assert "DCH" in html_text


def test_report_escapes_html(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    write_report(out, make_stats(), "<script>alert(1)</script>")
    html_text = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html_text
    assert "&lt;Unknownland&gt;" in html_text


def test_records_without_coordinates_get_no_marker(tmp_path: Path) -> None:
    stats = StatsCollector()
    stats.add(EnrichedIP(ip="203.0.113.5"))
    out = tmp_path / "report.html"
    write_report(out, stats, "x.log")
    assert "const markers = []" in out.read_text(encoding="utf-8")
