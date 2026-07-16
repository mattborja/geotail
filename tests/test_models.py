"""Tests for geotail.models."""

import dataclasses

import pytest

from geotail.models import EnrichedIP


def test_defaults_are_none_and_not_proxy() -> None:
    rec = EnrichedIP(ip="203.0.113.9")
    assert rec.country_code is None
    assert rec.city is None
    assert rec.latitude is None
    assert rec.is_proxy is False
    assert rec.raw == {}


def test_frozen() -> None:
    rec = EnrichedIP(ip="203.0.113.9")
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.city = "Oslo"  # type: ignore[misc]


def test_to_dict_round_trip() -> None:
    rec = EnrichedIP(
        ip="8.8.8.8",
        country_code="US",
        country_name="United States of America",
        region="California",
        city="Mountain View",
        latitude=37.4,
        longitude=-122.1,
        asn="AS15169",
        isp="Google LLC",
        is_proxy=True,
        proxy_type="DCH",
        usage_type="DCH",
        raw={"extra": 1},
    )
    data = rec.to_dict()
    assert data["ip"] == "8.8.8.8"
    assert data["country_code"] == "US"
    assert data["is_proxy"] is True
    assert data["proxy_type"] == "DCH"
    assert "raw" not in data  # raw is internal, not part of the JSONL schema
    assert set(data) == {
        "ip",
        "country_code",
        "country_name",
        "region",
        "city",
        "latitude",
        "longitude",
        "asn",
        "isp",
        "is_proxy",
        "proxy_type",
        "usage_type",
    }
