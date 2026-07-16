"""The enrichment engine: IP address -> ``EnrichedIP``.

Composes a geo provider and an optional proxy provider behind an LRU cache,
since real logs repeat the same IPs constantly. Handles IPv4 and IPv6, and
returns an empty-but-valid record for private, reserved, or invalid input —
never an exception.
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Any

from geotail.models import EnrichedIP
from geotail.providers.base import GeoProvider, ProxyProvider

_GEO_FIELDS = (
    "country_code",
    "country_name",
    "region",
    "city",
    "latitude",
    "longitude",
    "asn",
    "isp",
)
_PROXY_FIELDS = ("proxy_type", "usage_type")


class Enricher:
    """Merge geo + proxy provider output into a single ``EnrichedIP``."""

    def __init__(
        self,
        geo: GeoProvider,
        proxy: ProxyProvider | None = None,
        cache_size: int = 4096,
    ) -> None:
        self._geo = geo
        self._proxy = proxy
        self._enrich_cached = lru_cache(maxsize=cache_size)(self._enrich_uncached)

    def enrich(self, ip: str) -> EnrichedIP:
        """Enrich one IP address. Cached; safe for any input string."""
        return self._enrich_cached(ip.strip())

    def cache_info(self) -> Any:
        """Expose LRU cache statistics (hits, misses, currsize)."""
        return self._enrich_cached.cache_info()

    def _enrich_uncached(self, ip: str) -> EnrichedIP:
        try:
            parsed = ipaddress.ip_address(ip)
        except ValueError:
            return EnrichedIP(ip=ip, raw={"error": "invalid address"})
        if not parsed.is_global:
            return EnrichedIP(ip=ip, raw={"non_routable": True})

        geo = self._safe_lookup(self._geo, ip)
        proxy = self._safe_lookup(self._proxy, ip) if self._proxy is not None else {}

        # Geo DB wins for overlapping fields (asn/isp); proxy DB fills gaps.
        asn = geo.get("asn") or proxy.get("asn")
        isp = geo.get("isp") or proxy.get("isp")

        known = set(_GEO_FIELDS) | set(_PROXY_FIELDS) | {"is_proxy"}
        raw = {key: value for key, value in {**proxy, **geo}.items() if key not in known}

        return EnrichedIP(
            ip=ip,
            country_code=_opt_str(geo.get("country_code")),
            country_name=_opt_str(geo.get("country_name")),
            region=_opt_str(geo.get("region")),
            city=_opt_str(geo.get("city")),
            latitude=_opt_float(geo.get("latitude")),
            longitude=_opt_float(geo.get("longitude")),
            asn=_opt_str(asn),
            isp=_opt_str(isp),
            is_proxy=bool(proxy.get("is_proxy", False)),
            proxy_type=_opt_str(proxy.get("proxy_type")),
            usage_type=_opt_str(proxy.get("usage_type") or geo.get("usage_type")),
            raw=raw,
        )

    @staticmethod
    def _safe_lookup(provider: GeoProvider | ProxyProvider, ip: str) -> dict[str, Any]:
        try:
            result = provider.lookup(ip)
        except Exception:
            return {}
        return result if isinstance(result, dict) else {}


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
