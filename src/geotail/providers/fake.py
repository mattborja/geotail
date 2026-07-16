"""Deterministic in-memory providers for tests and ``--demo`` mode.

Seeded from plain dicts, so tests run with no network and no BIN files.
With ``synthesize=True`` unknown public IPs are deterministically mapped onto
the seed data (by hashing the IP), which keeps ``--demo`` interesting for any
input while staying fully reproducible.
"""

from __future__ import annotations

import hashlib
from typing import Any

from geotail.providers.ip2location import is_public_ip


class FakeGeoProvider:
    """Geolocation answers from an in-memory dict."""

    def __init__(self, data: dict[str, dict[str, Any]], synthesize: bool = False) -> None:
        self._data = data
        self._synthesize = synthesize

    def lookup(self, ip: str) -> dict[str, Any]:
        if ip in self._data:
            return dict(self._data[ip])
        if self._synthesize and self._data and is_public_ip(ip):
            return dict(_pick(self._data, ip))
        return {}


class FakeProxyProvider:
    """Proxy/threat answers from an in-memory dict."""

    def __init__(self, data: dict[str, dict[str, Any]], synthesize: bool = False) -> None:
        self._data = data
        self._synthesize = synthesize

    def lookup(self, ip: str) -> dict[str, Any]:
        if ip in self._data:
            return dict(self._data[ip])
        if self._synthesize and self._data and is_public_ip(ip):
            return dict(_pick(self._data, ip))
        return {}


def _pick(data: dict[str, dict[str, Any]], ip: str) -> dict[str, Any]:
    """Deterministically pick a seed record for an unknown IP."""
    digest = hashlib.sha256(ip.encode("utf-8")).digest()
    keys = sorted(data)
    return data[keys[digest[0] % len(keys)]]


DEMO_GEO_DATA: dict[str, dict[str, Any]] = {
    "8.8.8.8": {
        "country_code": "US",
        "country_name": "United States of America",
        "region": "California",
        "city": "Mountain View",
        "latitude": 37.386,
        "longitude": -122.084,
        "isp": "Google LLC",
        "asn": "AS15169",
    },
    "1.1.1.1": {
        "country_code": "AU",
        "country_name": "Australia",
        "region": "Queensland",
        "city": "South Brisbane",
        "latitude": -27.482,
        "longitude": 153.017,
        "isp": "Cloudflare Inc.",
        "asn": "AS13335",
    },
    "93.184.216.34": {
        "country_code": "US",
        "country_name": "United States of America",
        "region": "Massachusetts",
        "city": "Norwell",
        "latitude": 42.151,
        "longitude": -70.822,
        "isp": "Edgecast Inc.",
        "asn": "AS15133",
    },
    "185.220.101.34": {
        "country_code": "DE",
        "country_name": "Germany",
        "region": "Berlin",
        "city": "Berlin",
        "latitude": 52.52,
        "longitude": 13.405,
        "isp": "Zwiebelfreunde e.V.",
        "asn": "AS60729",
    },
    "45.155.205.233": {
        "country_code": "RU",
        "country_name": "Russian Federation",
        "region": "Moscow",
        "city": "Moscow",
        "latitude": 55.756,
        "longitude": 37.617,
        "isp": "HostSailor Ltd.",
        "asn": "AS208091",
    },
    "103.152.220.44": {
        "country_code": "CN",
        "country_name": "China",
        "region": "Beijing",
        "city": "Beijing",
        "latitude": 39.907,
        "longitude": 116.397,
        "isp": "Beijing Datacenter Ltd.",
        "asn": "AS4808",
    },
    "196.251.85.10": {
        "country_code": "ZA",
        "country_name": "South Africa",
        "region": "Gauteng",
        "city": "Johannesburg",
        "latitude": -26.204,
        "longitude": 28.047,
        "isp": "Vodacom Business",
        "asn": "AS36994",
    },
    "179.60.147.5": {
        "country_code": "BR",
        "country_name": "Brazil",
        "region": "Sao Paulo",
        "city": "Sao Paulo",
        "latitude": -23.551,
        "longitude": -46.633,
        "isp": "Telefonica Brasil",
        "asn": "AS27699",
    },
    "2606:4700:4700::1111": {
        "country_code": "US",
        "country_name": "United States of America",
        "region": "California",
        "city": "San Francisco",
        "latitude": 37.775,
        "longitude": -122.419,
        "isp": "Cloudflare Inc.",
        "asn": "AS13335",
    },
}

DEMO_PROXY_DATA: dict[str, dict[str, Any]] = {
    "8.8.8.8": {"is_proxy": True, "proxy_type": "DCH", "usage_type": "DCH"},
    "1.1.1.1": {"is_proxy": True, "proxy_type": "DCH", "usage_type": "CDN"},
    "93.184.216.34": {"is_proxy": False},
    "185.220.101.34": {"is_proxy": True, "proxy_type": "TOR", "usage_type": "DCH"},
    "45.155.205.233": {"is_proxy": True, "proxy_type": "VPN", "usage_type": "DCH"},
    "103.152.220.44": {"is_proxy": True, "proxy_type": "PUB", "usage_type": "DCH"},
    "196.251.85.10": {"is_proxy": False, "usage_type": "MOB"},
    "179.60.147.5": {"is_proxy": False, "usage_type": "ISP"},
    "2606:4700:4700::1111": {"is_proxy": True, "proxy_type": "DCH", "usage_type": "CDN"},
}


def demo_providers() -> tuple[FakeGeoProvider, FakeProxyProvider]:
    """Providers for ``--demo`` mode: seeded, synthesizing, zero external data."""
    return (
        FakeGeoProvider(DEMO_GEO_DATA, synthesize=True),
        FakeProxyProvider(DEMO_PROXY_DATA, synthesize=True),
    )
