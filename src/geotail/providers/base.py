"""Provider protocols.

The enrichment engine only depends on these two protocols, so it can run
against real IP2Location BIN files, an in-memory fake, or anything else that
answers ``lookup``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GeoProvider(Protocol):
    """Answers geolocation questions about an IP address.

    ``lookup`` returns a dict with any subset of the keys: ``country_code``,
    ``country_name``, ``region``, ``city``, ``latitude``, ``longitude``,
    ``asn``, ``isp``. Missing knowledge means a missing key or a ``None``
    value — never an exception.
    """

    def lookup(self, ip: str) -> dict[str, Any]: ...


@runtime_checkable
class ProxyProvider(Protocol):
    """Answers proxy/threat questions about an IP address.

    ``lookup`` returns a dict with any subset of the keys: ``is_proxy``
    (bool), ``proxy_type``, ``usage_type``, ``asn``, ``isp``, ``threat``.
    Missing knowledge means a missing key or a ``None`` value — never an
    exception.
    """

    def lookup(self, ip: str) -> dict[str, Any]: ...
