"""Providers backed by local IP2Location / IP2Proxy BIN databases.

Each provider opens its BIN file once and reuses the handle. All library
errors and sentinel values ("NOT SUPPORTED", "INVALID IP ADDRESS", "-",
"This parameter is unavailable ...") are normalized to absent fields, so a
country-only LITE database and a full commercial database both work.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

import IP2Location
import IP2Proxy

# Values the IP2Location/IP2Proxy libraries use to mean "no data".
_SENTINEL_PREFIXES = ("this parameter is unavailable",)
_SENTINEL_VALUES = {"", "-", "not supported", "invalid ip address", "n/a"}


def _clean(value: Any) -> Any:
    """Map library sentinel values to ``None``; pass real values through."""
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _SENTINEL_VALUES:
            return None
        if lowered.startswith(_SENTINEL_PREFIXES):
            return None
        return value.strip()
    return value


def _clean_float(value: Any) -> float | None:
    """Coerce a cleaned value to float, or ``None`` if impossible."""
    cleaned = _clean(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def is_public_ip(ip: str) -> bool:
    """True only for syntactically valid, globally routable addresses."""
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return parsed.is_global


class IP2LocationGeoProvider:
    """Geolocation lookups from an IP2Location BIN file (e.g. LITE DB11)."""

    def __init__(self, db_path: str | Path) -> None:
        self._db = IP2Location.IP2Location(str(db_path))

    def lookup(self, ip: str) -> dict[str, Any]:
        if not is_public_ip(ip):
            return {}
        try:
            record = self._db.get_all(ip)
        except Exception:
            return {}
        if record is None:
            return {}
        result: dict[str, Any] = {
            "country_code": _clean(getattr(record, "country_short", None)),
            "country_name": _clean(getattr(record, "country_long", None)),
            "region": _clean(getattr(record, "region", None)),
            "city": _clean(getattr(record, "city", None)),
            "latitude": _clean_float(getattr(record, "latitude", None)),
            "longitude": _clean_float(getattr(record, "longitude", None)),
            "isp": _clean(getattr(record, "isp", None)),
            "asn": _clean(getattr(record, "asn", None)),
        }
        return {key: value for key, value in result.items() if value is not None}


class IP2ProxyProvider:
    """Proxy/threat lookups from an IP2Proxy BIN file (e.g. LITE PX11)."""

    def __init__(self, db_path: str | Path) -> None:
        self._db = IP2Proxy.IP2Proxy(str(db_path))

    def lookup(self, ip: str) -> dict[str, Any]:
        if not is_public_ip(ip):
            return {}
        try:
            record = self._db.get_all(ip)
        except Exception:
            return {}
        if not record:
            return {}
        # get_all returns a dict; is_proxy is 1/2 for proxies, 0 for clean,
        # -1 for errors/invalid input.
        proxy_flag = record.get("is_proxy", -1)
        result: dict[str, Any] = {
            "proxy_type": _clean(record.get("proxy_type")),
            "usage_type": _clean(record.get("usage_type")),
            "asn": _format_asn(_clean(record.get("asn"))),
            "isp": _clean(record.get("isp")),
            "threat": _clean(record.get("threat")),
        }
        cleaned = {key: value for key, value in result.items() if value is not None}
        if isinstance(proxy_flag, int) and proxy_flag > 0:
            cleaned["is_proxy"] = True
        elif proxy_flag == 0:
            cleaned["is_proxy"] = False
        return cleaned


def _format_asn(value: Any) -> str | None:
    """Render a bare AS number like ``15169`` as ``AS15169``."""
    if value is None:
        return None
    text = str(value)
    return text if text.upper().startswith("AS") else f"AS{text}"
