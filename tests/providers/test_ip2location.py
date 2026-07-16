"""Tests for geotail.providers.ip2location.

Normalization helpers are pure functions tested without any BIN file; the
real database round-trips are integration tests that skip automatically when
no BIN is present, so CI stays green with no downloads.
"""

import os
from pathlib import Path

import pytest

from geotail.providers.ip2location import _clean, _clean_float, _format_asn, is_public_ip


class TestClean:
    def test_passes_real_values(self) -> None:
        assert _clean("Mountain View") == "Mountain View"
        assert _clean(37.4) == 37.4

    def test_strips_whitespace(self) -> None:
        assert _clean("  Oslo ") == "Oslo"

    @pytest.mark.parametrize(
        "sentinel",
        [
            None,
            "",
            "-",
            "N/A",
            "NOT SUPPORTED",
            "INVALID IP ADDRESS",
            "This parameter is unavailable in selected .BIN data file. "
            "Please upgrade data file.",
        ],
    )
    def test_sentinels_become_none(self, sentinel: str | None) -> None:
        assert _clean(sentinel) is None


class TestCleanFloat:
    def test_string_coercion(self) -> None:
        assert _clean_float("37.4") == 37.4

    def test_sentinel_and_garbage(self) -> None:
        assert _clean_float("NOT SUPPORTED") is None
        assert _clean_float("not-a-float") is None
        assert _clean_float(None) is None


class TestFormatAsn:
    def test_bare_number_gets_prefix(self) -> None:
        assert _format_asn("15169") == "AS15169"
        assert _format_asn(15169) == "AS15169"

    def test_prefixed_left_alone(self) -> None:
        assert _format_asn("AS15169") == "AS15169"

    def test_none(self) -> None:
        assert _format_asn(None) is None


class TestIsPublicIp:
    def test_public(self) -> None:
        assert is_public_ip("8.8.8.8")
        assert is_public_ip("2606:4700:4700::1111")

    @pytest.mark.parametrize(
        "ip", ["10.0.0.1", "192.168.1.1", "127.0.0.1", "::1", "fe80::1", "garbage", ""]
    )
    def test_private_reserved_invalid(self, ip: str) -> None:
        assert not is_public_ip(ip)


def _find_bin(env_var: str, prefix: str) -> Path | None:
    env = os.environ.get(env_var)
    if env and Path(env).is_file():
        return Path(env)
    data_dir = Path("data")
    if data_dir.is_dir():
        for entry in sorted(data_dir.iterdir()):
            if entry.name.upper().startswith(prefix) and entry.name.upper().endswith(".BIN"):
                return entry
    return None


_GEO_BIN = _find_bin("IP2LOCATION_DB", "IP2LOCATION")
_PROXY_BIN = _find_bin("IP2PROXY_DB", "IP2PROXY")


@pytest.mark.integration
@pytest.mark.skipif(_GEO_BIN is None, reason="no IP2Location BIN file present")
def test_real_geo_lookup() -> None:
    from geotail.providers.ip2location import IP2LocationGeoProvider

    assert _GEO_BIN is not None
    provider = IP2LocationGeoProvider(_GEO_BIN)
    result = provider.lookup("8.8.8.8")
    assert result.get("country_code") == "US"
    assert provider.lookup("192.168.1.1") == {}
    assert provider.lookup("bogus") == {}


@pytest.mark.integration
@pytest.mark.skipif(_PROXY_BIN is None, reason="no IP2Proxy BIN file present")
def test_real_proxy_lookup() -> None:
    from geotail.providers.ip2location import IP2ProxyProvider

    assert _PROXY_BIN is not None
    provider = IP2ProxyProvider(_PROXY_BIN)
    result = provider.lookup("8.8.8.8")
    assert isinstance(result, dict)
    assert provider.lookup("10.0.0.1") == {}
