"""Tests for geotail.providers.base."""

from geotail.providers.base import GeoProvider, ProxyProvider
from geotail.providers.fake import FakeGeoProvider, FakeProxyProvider


def test_fake_geo_satisfies_protocol() -> None:
    assert isinstance(FakeGeoProvider({}), GeoProvider)


def test_fake_proxy_satisfies_protocol() -> None:
    assert isinstance(FakeProxyProvider({}), ProxyProvider)


def test_non_provider_rejected() -> None:
    class NoLookup:
        pass

    assert not isinstance(NoLookup(), GeoProvider)
    assert not isinstance(NoLookup(), ProxyProvider)
