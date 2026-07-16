"""Tests for geotail.engine."""

from typing import Any

from geotail.engine import Enricher
from geotail.providers.fake import FakeGeoProvider, FakeProxyProvider

GEO = {
    "8.8.8.8": {
        "country_code": "US",
        "country_name": "United States of America",
        "region": "California",
        "city": "Mountain View",
        "latitude": 37.4,
        "longitude": -122.1,
        "isp": "Google LLC",
        "asn": "AS15169",
    },
    "2606:4700:4700::1111": {"country_code": "US", "city": "San Francisco"},
}
PROXY = {
    "8.8.8.8": {"is_proxy": True, "proxy_type": "DCH", "usage_type": "DCH"},
    "2606:4700:4700::1111": {"is_proxy": True, "proxy_type": "DCH"},
}


class CountingGeo:
    """Fake geo provider that counts lookups, for cache assertions."""

    def __init__(self, data: dict[str, dict[str, Any]]) -> None:
        self.calls = 0
        self._inner = FakeGeoProvider(data)

    def lookup(self, ip: str) -> dict[str, Any]:
        self.calls += 1
        return self._inner.lookup(ip)


def make_enricher() -> Enricher:
    return Enricher(FakeGeoProvider(GEO), FakeProxyProvider(PROXY))


def test_merges_geo_and_proxy() -> None:
    rec = make_enricher().enrich("8.8.8.8")
    assert rec.country_code == "US"
    assert rec.city == "Mountain View"
    assert rec.latitude == 37.4
    assert rec.asn == "AS15169"
    assert rec.is_proxy is True
    assert rec.proxy_type == "DCH"


def test_ipv6() -> None:
    rec = make_enricher().enrich("2606:4700:4700::1111")
    assert rec.country_code == "US"
    assert rec.is_proxy is True


def test_missing_fields_become_none() -> None:
    rec = make_enricher().enrich("2606:4700:4700::1111")
    assert rec.region is None
    assert rec.latitude is None
    assert rec.usage_type is None


def test_private_ip_is_empty_but_valid() -> None:
    rec = make_enricher().enrich("192.168.0.1")
    assert rec.ip == "192.168.0.1"
    assert rec.country_code is None
    assert rec.is_proxy is False
    assert rec.raw.get("non_routable") is True


def test_invalid_ip_never_raises() -> None:
    rec = make_enricher().enrich("definitely-not-an-ip")
    assert rec.ip == "definitely-not-an-ip"
    assert rec.country_code is None
    assert rec.raw.get("error") == "invalid address"


def test_lookup_is_cached() -> None:
    geo = CountingGeo(GEO)
    enricher = Enricher(geo, FakeProxyProvider(PROXY))
    for _ in range(5):
        enricher.enrich("8.8.8.8")
    assert geo.calls == 1
    assert enricher.cache_info().hits == 4


def test_input_is_stripped_before_caching() -> None:
    geo = CountingGeo(GEO)
    enricher = Enricher(geo, None)
    assert enricher.enrich(" 8.8.8.8 ").city == "Mountain View"
    enricher.enrich("8.8.8.8")
    assert geo.calls == 1


def test_works_without_proxy_provider() -> None:
    rec = Enricher(FakeGeoProvider(GEO), None).enrich("8.8.8.8")
    assert rec.country_code == "US"
    assert rec.is_proxy is False
    assert rec.proxy_type is None


def test_raising_provider_is_contained() -> None:
    class Explosive:
        def lookup(self, ip: str) -> dict[str, Any]:
            raise RuntimeError("boom")

    rec = Enricher(Explosive(), Explosive()).enrich("8.8.8.8")
    assert rec.country_code is None
    assert rec.is_proxy is False


def test_unknown_extra_fields_land_in_raw() -> None:
    geo = FakeGeoProvider({"8.8.8.8": {"country_code": "US", "elevation": 32}})
    rec = Enricher(geo, None).enrich("8.8.8.8")
    assert rec.raw == {"elevation": 32}
