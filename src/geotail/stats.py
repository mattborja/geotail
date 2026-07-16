"""Rolling aggregates over a stream of enriched events."""

from __future__ import annotations

from collections import Counter
from typing import NamedTuple

from geotail.models import EnrichedIP


class Offender(NamedTuple):
    """One row of the top-offenders table."""

    ip: str
    hits: int
    enriched: EnrichedIP


class StatsCollector:
    """Maintains counts by country, ASN, and proxy type over a stream."""

    def __init__(self) -> None:
        self.total: int = 0
        self.proxy_count: int = 0
        self.parse_failures: int = 0
        self._by_country: Counter[str] = Counter()
        self._by_asn: Counter[str] = Counter()
        self._by_proxy_type: Counter[str] = Counter()
        self._by_ip: Counter[str] = Counter()
        self._latest: dict[str, EnrichedIP] = {}

    def add(self, record: EnrichedIP) -> None:
        """Fold one enriched event into the aggregates."""
        self.total += 1
        if record.is_proxy:
            self.proxy_count += 1
            self._by_proxy_type[record.proxy_type or "unknown"] += 1
        self._by_country[record.country_name or "unknown"] += 1
        asn_label = _asn_label(record)
        if asn_label is not None:
            self._by_asn[asn_label] += 1
        self._by_ip[record.ip] += 1
        self._latest[record.ip] = record

    @property
    def proxy_ratio(self) -> float:
        """Fraction of events flagged as proxy traffic (0.0 when empty)."""
        return self.proxy_count / self.total if self.total else 0.0

    @property
    def unique_ips(self) -> int:
        return len(self._by_ip)

    def top_countries(self, n: int = 10) -> list[tuple[str, int]]:
        return self._by_country.most_common(n)

    def top_asns(self, n: int = 10) -> list[tuple[str, int]]:
        return self._by_asn.most_common(n)

    def proxy_types(self) -> list[tuple[str, int]]:
        return self._by_proxy_type.most_common()

    def top_offenders(self, n: int = 10) -> list[Offender]:
        return [
            Offender(ip, count, self._latest[ip]) for ip, count in self._by_ip.most_common(n)
        ]

    def all_records(self) -> list[Offender]:
        """Every unique IP with its hit count, most frequent first."""
        return self.top_offenders(len(self._by_ip))


def _asn_label(record: EnrichedIP) -> str | None:
    if record.asn and record.isp:
        return f"{record.asn} {record.isp}"
    return record.asn or record.isp
