"""Typed schema for enriched IP records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EnrichedIP:
    """A single IP address enriched with geolocation and proxy intelligence.

    Any field the loaded database does not carry is ``None`` rather than an
    error — the schema is tolerant of country-only and full databases alike.
    """

    ip: str
    country_code: str | None = None
    country_name: str | None = None
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    asn: str | None = None
    isp: str | None = None
    is_proxy: bool = False
    proxy_type: str | None = None
    usage_type: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict of the enriched record."""
        return {
            "ip": self.ip,
            "country_code": self.country_code,
            "country_name": self.country_name,
            "region": self.region,
            "city": self.city,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "asn": self.asn,
            "isp": self.isp,
            "is_proxy": self.is_proxy,
            "proxy_type": self.proxy_type,
            "usage_type": self.usage_type,
        }
