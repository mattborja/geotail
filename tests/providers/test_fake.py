"""Tests for geotail.providers.fake."""

from geotail.providers.fake import (
    DEMO_GEO_DATA,
    DEMO_PROXY_DATA,
    FakeGeoProvider,
    FakeProxyProvider,
    demo_providers,
)


def test_seeded_lookup_returns_copy() -> None:
    provider = FakeGeoProvider({"8.8.8.8": {"city": "Mountain View"}})
    result = provider.lookup("8.8.8.8")
    assert result == {"city": "Mountain View"}
    result["city"] = "mutated"
    assert provider.lookup("8.8.8.8") == {"city": "Mountain View"}


def test_unknown_ip_returns_empty_without_synthesize() -> None:
    provider = FakeGeoProvider({"8.8.8.8": {"city": "Mountain View"}})
    assert provider.lookup("203.0.113.99") == {}


def test_synthesize_is_deterministic_and_draws_from_seed() -> None:
    provider = FakeGeoProvider(DEMO_GEO_DATA, synthesize=True)
    first = provider.lookup("34.117.59.81")
    second = provider.lookup("34.117.59.81")
    assert first == second
    assert first in list(DEMO_GEO_DATA.values())


def test_synthesize_skips_private_and_invalid_ips() -> None:
    provider = FakeProxyProvider(DEMO_PROXY_DATA, synthesize=True)
    assert provider.lookup("192.168.1.1") == {}
    assert provider.lookup("not-an-ip") == {}


def test_demo_providers_cover_demo_data() -> None:
    geo, proxy = demo_providers()
    assert geo.lookup("8.8.8.8")["country_code"] == "US"
    assert proxy.lookup("185.220.101.34")["proxy_type"] == "TOR"


def test_demo_datasets_are_aligned() -> None:
    assert set(DEMO_GEO_DATA) == set(DEMO_PROXY_DATA)
