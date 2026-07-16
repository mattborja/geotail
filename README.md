# geotail

**Pipe your server logs in, get a live map of who's knocking — fully offline.**

`geotail` reads server logs, enriches every source IP with geolocation and proxy/VPN/Tor
intelligence from local [IP2Location LITE](https://lite.ip2location.com) databases, and renders a
live terminal dashboard of where traffic comes from and how much of it is suspicious. No API keys,
no network calls, no data leaving your box.

![geotail live dashboard](docs/demo.gif)

*`tail -f access.log | geotail` — countries, networks, and proxy-flagged offenders updating live.*

## 30-second quickstart

```bash
pipx install geotail   # or: pip install geotail / uvx geotail
geotail --demo         # live dashboard, zero external files needed
```

For real lookups, download two free LITE databases from
**<https://lite.ip2location.com>** (free account, no credit card, attribution required):

1. `IP2LOCATION-LITE-DB11.BIN` — geolocation (required)
2. `IP2PROXY-LITE-PX11.BIN` — proxy/VPN/Tor detection (optional but recommended)

Drop both into `./data/` and run:

```bash
geotail --file sample.log            # bundled sample traffic
tail -f /var/log/nginx/access.log | geotail
geotail --file auth.log --json > enriched.jsonl
geotail --file sample.log --report report.html
```

> **Note:** IP2Proxy LITE covers public proxies; the commercial database adds
> VPN/Tor/datacenter/residential classification for richer results. geotail reads whatever fields
> your BIN tier provides and quietly omits the rest — a country-only DB works fine too.

## Features

- **Offline-first** — every lookup comes from local BIN files; zero network calls in the
  enrichment path.
- **Live TUI dashboard** — top countries, top networks (ASN/ISP), and a top-offenders table with
  proxy/VPN/Tor flags, streaming as lines arrive.
- **Log-format aware** — auto-detects nginx/apache combined, sshd/auth.log, and a generic
  first-IP fallback; or force with `--format` / bring your own `--regex`.
- **JSONL mode** — `--json` emits one enriched record per line for jq/SIEM pipelines
  (automatically the default when stdout is piped).
- **HTML report** — `--report out.html` writes a self-contained page with a Leaflet world map and
  summary tables.
- **tail -f built in** — `--file x.log --follow` keeps reading as the file grows, and survives
  logrotate truncation.
- **IPv4 + IPv6**, LRU-cached lookups, graceful handling of private/invalid IPs, clean Ctrl-C.
- **Demo mode** — `--demo` runs on bundled deterministic fake data, so you can try everything
  before downloading a single database.

## CLI reference

```
geotail [SOURCE] [OPTIONS]

Sources (default: stdin):
  SOURCE / --file PATH    read from a file instead of stdin

Options:
  --format {auto,nginx,apache,sshd,generic}   log format (default: auto)
  --regex PATTERN         custom IP-extraction regex (implies generic)
  --geo-db PATH           IP2Location BIN (else $IP2LOCATION_DB, else ./data/)
  --proxy-db PATH         IP2Proxy BIN (else $IP2PROXY_DB, else ./data/; optional)
  --json                  emit enriched JSONL instead of the TUI
  --tui                   force the live dashboard even when piped
  --report PATH           write a static HTML report on exit
  --follow                keep reading as the file grows (tail -f)
  --top N                 rows in top-N panels (default 10)
  --demo                  run against bundled fake data, no BIN needed
  --about                 print version + IP2Location attribution
```

The TUI is the default when stdout is a terminal; JSONL is the default when piped. `--json` and
`--tui` force one or the other (and are mutually exclusive).

### Example JSONL record

```json
{"ip": "185.220.101.34", "country_code": "DE", "country_name": "Germany", "region": "Berlin",
 "city": "Berlin", "latitude": 52.52, "longitude": 13.405, "asn": "AS60729",
 "isp": "Zwiebelfreunde e.V.", "is_proxy": true, "proxy_type": "TOR", "usage_type": "DCH",
 "ts": "2026-07-15T10:00:07+00:00"}
```

Fields the loaded database doesn't carry are `null` — never an error.

## How it works

```
log lines ──▶ parsers.py ──▶ engine.Enricher ──▶ stats.StatsCollector ──▶ tui / JSONL / report
              (nginx, sshd,       │  LRU cache
               generic, regex)    ▼
                        GeoProvider + ProxyProvider   (typing.Protocol seam)
                        ├─ ip2location.py  ← local IP2Location / IP2Proxy BIN files
                        └─ fake.py         ← deterministic in-memory data (--demo, tests)
```

The enrichment engine only knows about two tiny `Protocol`s (`GeoProvider`, `ProxyProvider`), each
with a single `lookup(ip) -> dict` method. The real implementations wrap the official
[IP2Location](https://pypi.org/project/IP2Location/) and
[IP2Proxy](https://pypi.org/project/IP2Proxy/) libraries reading local BIN files; the fake
implementation powers `--demo` and the entire test suite, which runs with no network and no
proprietary data. Library sentinel values ("NOT SUPPORTED", "This parameter is unavailable…") are
normalized to `None`, so any LITE tier — country-only through DB11/PX11 — works unchanged.

Use it as a library, too:

```python
from geotail import Enricher
from geotail.providers.ip2location import IP2LocationGeoProvider, IP2ProxyProvider

enricher = Enricher(
    IP2LocationGeoProvider("data/IP2LOCATION-LITE-DB11.BIN"),
    IP2ProxyProvider("data/IP2PROXY-LITE-PX11.BIN"),
)
record = enricher.enrich("8.8.8.8")
print(record.country_name, record.is_proxy, record.to_dict())
```

## Development

```bash
pip install -e '.[dev]'
pytest          # 100+ tests, no network, no BIN files needed
mypy            # strict
ruff check src tests
```

Integration tests against real BIN files are marked `integration` and skip automatically when no
database is present in `./data/`.

## Attribution

> This site or product includes IP2Location LITE data available from
> <https://lite.ip2location.com>.

## License & contributing

MIT — see [LICENSE](LICENSE). Issues and pull requests welcome; please keep the test suite green
(`pytest`, `mypy`, `ruff`) and add tests alongside any new module.
