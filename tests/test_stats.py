"""Tests for geotail.stats."""

from geotail.models import EnrichedIP
from geotail.stats import StatsCollector

US_PROXY = EnrichedIP(
    ip="8.8.8.8",
    country_name="United States of America",
    country_code="US",
    asn="AS15169",
    isp="Google LLC",
    is_proxy=True,
    proxy_type="DCH",
)
DE_TOR = EnrichedIP(
    ip="185.220.101.34",
    country_name="Germany",
    country_code="DE",
    asn="AS60729",
    is_proxy=True,
    proxy_type="TOR",
)
BR_CLEAN = EnrichedIP(
    ip="179.60.147.5",
    country_name="Brazil",
    country_code="BR",
    isp="Telefonica Brasil",
)
UNKNOWN = EnrichedIP(ip="192.168.1.1")


def collect(*records: EnrichedIP) -> StatsCollector:
    stats = StatsCollector()
    for record in records:
        stats.add(record)
    return stats


def test_empty_collector() -> None:
    stats = StatsCollector()
    assert stats.total == 0
    assert stats.proxy_ratio == 0.0
    assert stats.top_countries() == []
    assert stats.top_offenders() == []


def test_totals_and_proxy_ratio() -> None:
    stats = collect(US_PROXY, US_PROXY, DE_TOR, BR_CLEAN)
    assert stats.total == 4
    assert stats.proxy_count == 3
    assert stats.proxy_ratio == 0.75
    assert stats.unique_ips == 3


def test_country_aggregation() -> None:
    stats = collect(US_PROXY, US_PROXY, DE_TOR, BR_CLEAN, UNKNOWN)
    assert stats.top_countries(2) == [("United States of America", 2), ("Germany", 1)]
    assert dict(stats.top_countries(10))["unknown"] == 1


def test_asn_label_combines_asn_and_isp() -> None:
    stats = collect(US_PROXY, BR_CLEAN, UNKNOWN)
    labels = dict(stats.top_asns(10))
    assert labels["AS15169 Google LLC"] == 1
    assert labels["Telefonica Brasil"] == 1  # isp-only record still counted
    assert len(labels) == 2  # record with neither asn nor isp is excluded


def test_proxy_type_breakdown() -> None:
    stats = collect(US_PROXY, US_PROXY, DE_TOR, BR_CLEAN)
    assert stats.proxy_types() == [("DCH", 2), ("TOR", 1)]


def test_top_offenders_ordering_and_enrichment() -> None:
    stats = collect(DE_TOR, US_PROXY, DE_TOR, DE_TOR, BR_CLEAN)
    offenders = stats.top_offenders(2)
    assert [(o.ip, o.hits) for o in offenders] == [("185.220.101.34", 3), ("8.8.8.8", 1)]
    assert offenders[0].enriched.proxy_type == "TOR"


def test_top_n_truncation() -> None:
    stats = collect(US_PROXY, DE_TOR, BR_CLEAN)
    assert len(stats.top_countries(1)) == 1
    assert len(stats.top_offenders(1)) == 1
    assert len(stats.all_records()) == 3
