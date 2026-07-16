"""Tests for geotail.parsers."""

from datetime import UTC, datetime

import pytest

from geotail.parsers import (
    get_parser,
    make_regex_parser,
    parse_auto,
    parse_generic,
    parse_nginx,
    parse_sshd,
)

NGINX_LINE = (
    '203.0.113.7 - - [15/Jul/2026:10:00:00 +0000] "GET /index.html HTTP/1.1" '
    '200 1234 "-" "curl/8.5.0"'
)
APACHE_LINE = (
    '198.51.100.3 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326'
)
SSHD_FAILED = (
    "Jul 15 10:12:01 bastion sshd[4242]: Failed password for root "
    "from 203.0.113.99 port 51234 ssh2"
)
SSHD_ACCEPTED = (
    "Jul 15 10:13:44 bastion sshd[4243]: Accepted publickey for deploy "
    "from 198.51.100.7 port 40022 ssh2"
)


class TestNginx:
    def test_ip_and_timestamp(self) -> None:
        parsed = parse_nginx(NGINX_LINE)
        assert parsed is not None
        assert parsed.ip == "203.0.113.7"
        assert parsed.timestamp == datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)

    def test_apache_combined_variant(self) -> None:
        parsed = parse_nginx(APACHE_LINE)
        assert parsed is not None
        assert parsed.ip == "198.51.100.3"

    def test_rejects_non_combined(self) -> None:
        assert parse_nginx(SSHD_FAILED) is None
        assert parse_nginx("garbage line") is None

    def test_rejects_invalid_ip_field(self) -> None:
        assert parse_nginx('not-an-ip - - [15/Jul/2026:10:00:00 +0000] "GET / HTTP/1.1"') is None

    def test_bad_timestamp_still_yields_ip(self) -> None:
        parsed = parse_nginx('203.0.113.7 - - [bogus timestamp] "GET / HTTP/1.1" 200 5')
        assert parsed is not None
        assert parsed.ip == "203.0.113.7"
        assert parsed.timestamp is None


class TestSshd:
    def test_failed_password(self) -> None:
        parsed = parse_sshd(SSHD_FAILED)
        assert parsed is not None
        assert parsed.ip == "203.0.113.99"
        assert parsed.timestamp is not None
        assert (parsed.timestamp.month, parsed.timestamp.day) == (7, 15)

    def test_accepted(self) -> None:
        parsed = parse_sshd(SSHD_ACCEPTED)
        assert parsed is not None
        assert parsed.ip == "198.51.100.7"

    def test_ipv6(self) -> None:
        line = "Jul 15 10:14:00 bastion sshd[1]: Failed password from 2001:db8::5 port 22 ssh2"
        parsed = parse_sshd(line)
        assert parsed is not None
        assert parsed.ip == "2001:db8::5"

    def test_no_from_clause(self) -> None:
        assert parse_sshd("Jul 15 10:14:00 bastion sshd[1]: Connection closed") is None


class TestGeneric:
    def test_first_ip_token(self) -> None:
        parsed = parse_generic("weird log: client=203.0.113.5, done")
        assert parsed is not None
        assert parsed.ip == "203.0.113.5"

    def test_plain_ip(self) -> None:
        parsed = parse_generic("blocked 198.51.100.23 after 5 attempts")
        assert parsed is not None
        assert parsed.ip == "198.51.100.23"

    def test_ipv6_in_brackets(self) -> None:
        parsed = parse_generic("client [2001:db8::7] connected")
        assert parsed is not None
        assert parsed.ip == "2001:db8::7"

    def test_no_ip(self) -> None:
        assert parse_generic("nothing to see here 12345") is None
        assert parse_generic("") is None

    def test_version_number_not_mistaken_for_ip(self) -> None:
        parsed = parse_generic("agent v1.2.3 started")
        assert parsed is None


class TestRegexParser:
    def test_named_group(self) -> None:
        parse = make_regex_parser(r"src=(?P<ip>\S+)")
        parsed = parse("blah src=203.0.113.44 dst=x")
        assert parsed is not None
        assert parsed.ip == "203.0.113.44"

    def test_positional_group(self) -> None:
        parse = make_regex_parser(r"client (\S+) connected")
        parsed = parse("client 198.51.100.9 connected")
        assert parsed is not None
        assert parsed.ip == "198.51.100.9"

    def test_whole_match(self) -> None:
        parse = make_regex_parser(r"\d+\.\d+\.\d+\.\d+")
        parsed = parse("x 203.0.113.1 y")
        assert parsed is not None
        assert parsed.ip == "203.0.113.1"

    def test_match_that_is_not_an_ip(self) -> None:
        parse = make_regex_parser(r"src=(\S+)")
        assert parse("src=hostname.example") is None


class TestAutoAndRegistry:
    def test_auto_detects_each_format(self) -> None:
        for line, ip in [
            (NGINX_LINE, "203.0.113.7"),
            (SSHD_FAILED, "203.0.113.99"),
            ("some 198.51.100.1 thing", "198.51.100.1"),
        ]:
            parsed = parse_auto(line)
            assert parsed is not None
            assert parsed.ip == ip

    def test_auto_skips_garbage(self) -> None:
        assert parse_auto("completely unparseable") is None

    def test_get_parser_by_name(self) -> None:
        assert get_parser("nginx") is parse_nginx
        assert get_parser("apache") is parse_nginx
        assert get_parser("sshd") is parse_sshd
        assert get_parser("auto") is parse_auto

    def test_get_parser_regex_overrides_format(self) -> None:
        parse = get_parser("nginx", regex=r"(?P<ip>\d+\.\d+\.\d+\.\d+)")
        parsed = parse("plain 203.0.113.2 text")
        assert parsed is not None
        assert parsed.ip == "203.0.113.2"

    def test_get_parser_unknown_format(self) -> None:
        with pytest.raises(ValueError):
            get_parser("csv")
