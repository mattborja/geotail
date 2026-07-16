"""Pluggable log-line parsers: line -> (ip, timestamp | None).

Formats: nginx/apache combined, sshd/auth.log, and a generic first-IP-token
fallback (optionally driven by a user-supplied regex). Unparseable lines
yield ``None`` and are skipped by callers, never fatal.
"""

from __future__ import annotations

import contextlib
import ipaddress
import re
from collections.abc import Callable
from datetime import datetime
from typing import NamedTuple


class ParsedLine(NamedTuple):
    """The extraction result for one log line."""

    ip: str
    timestamp: datetime | None


LineParser = Callable[[str], ParsedLine | None]

# nginx/apache combined: `1.2.3.4 - user [15/Jul/2026:10:00:00 +0000] "GET ..."`
_COMBINED_RE = re.compile(r"^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+\"")

# sshd: `Failed password for root from 1.2.3.4 port 22 ssh2`
_SSHD_RE = re.compile(r"\bfrom\s+(?P<ip>[0-9a-fA-F:.]+)(?:\s+port\b|\s*$)")
# syslog prefix: `Jul 15 10:00:00 host sshd[123]:`
_SYSLOG_TS_RE = re.compile(r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s")

_TOKEN_SPLIT_RE = re.compile(r"[\s,;=\"'()\[\]<>]+")


def _valid_ip(candidate: str) -> str | None:
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


def parse_nginx(line: str) -> ParsedLine | None:
    """Parse nginx/apache combined log format."""
    match = _COMBINED_RE.match(line)
    if match is None:
        return None
    ip = _valid_ip(match.group("ip"))
    if ip is None:
        return None
    timestamp: datetime | None = None
    with contextlib.suppress(ValueError):
        timestamp = datetime.strptime(match.group("ts"), "%d/%b/%Y:%H:%M:%S %z")
    return ParsedLine(ip, timestamp)


def parse_sshd(line: str) -> ParsedLine | None:
    """Parse sshd/auth.log lines ("Failed password ... from <ip>")."""
    match = _SSHD_RE.search(line)
    if match is None:
        return None
    ip = _valid_ip(match.group("ip"))
    if ip is None:
        return None
    timestamp: datetime | None = None
    ts_match = _SYSLOG_TS_RE.match(line)
    if ts_match is not None:
        try:
            parsed = datetime.strptime(ts_match.group("ts"), "%b %d %H:%M:%S")
            timestamp = parsed.replace(year=datetime.now().year)
        except ValueError:
            pass
    return ParsedLine(ip, timestamp)


def parse_generic(line: str) -> ParsedLine | None:
    """Extract the first IP-looking token anywhere in the line."""
    for token in _TOKEN_SPLIT_RE.split(line):
        candidate = token.strip(".,:;")
        if not candidate:
            continue
        # `strip` above removes trailing punctuation but would also mangle
        # IPv6; try the raw token first, then the stripped one.
        ip = _valid_ip(token) or _valid_ip(candidate)
        if ip is not None:
            return ParsedLine(ip, None)
    return None


def make_regex_parser(pattern: str) -> LineParser:
    """Build a parser from a user regex.

    The IP is taken from the group named ``ip``, else group 1, else the whole
    match.
    """
    compiled = re.compile(pattern)

    def parse(line: str) -> ParsedLine | None:
        match = compiled.search(line)
        if match is None:
            return None
        if "ip" in compiled.groupindex:
            candidate = match.group("ip")
        elif compiled.groups >= 1:
            candidate = match.group(1)
        else:
            candidate = match.group(0)
        ip = _valid_ip(candidate)
        return None if ip is None else ParsedLine(ip, None)

    return parse


def parse_auto(line: str) -> ParsedLine | None:
    """Try each format in specificity order; first hit wins."""
    return parse_nginx(line) or parse_sshd(line) or parse_generic(line)


PARSERS: dict[str, LineParser] = {
    "auto": parse_auto,
    "nginx": parse_nginx,
    "apache": parse_nginx,  # same combined log format
    "sshd": parse_sshd,
    "generic": parse_generic,
}


def get_parser(fmt: str, regex: str | None = None) -> LineParser:
    """Resolve a parser by format name; a custom regex overrides the format."""
    if regex is not None:
        return make_regex_parser(regex)
    try:
        return PARSERS[fmt]
    except KeyError:
        raise ValueError(f"unknown log format: {fmt!r}") from None
