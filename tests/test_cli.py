"""Tests for geotail.cli: argument wiring, source selection, output modes."""

import io
import json
import os
from pathlib import Path

import pytest

import geotail
from geotail.cli import build_arg_parser, main, resolve_db_path

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IP2LOCATION_DB", raising=False)
    monkeypatch.delenv("IP2PROXY_DB", raising=False)


class TestAbout:
    def test_about_prints_version_and_attribution(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--about"]) == 0
        out = capsys.readouterr().out
        assert geotail.__version__ in out
        assert "uses the IP2Location LITE database" in out
        assert "https://lite.ip2location.com" in out


class TestArgValidation:
    def test_json_and_tui_are_mutually_exclusive(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--demo", "--json", "--tui"]) == 2
        assert "mutually exclusive" in capsys.readouterr().err

    def test_positional_and_file_conflict(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--demo", "a.log", "--file", "b.log"]) == 2
        assert "not both" in capsys.readouterr().err

    def test_top_must_be_positive(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--demo", "--top", "0"]) == 2
        assert "--top" in capsys.readouterr().err

    def test_follow_requires_file(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        assert main(["--demo", "--follow", "--json"]) == 2
        assert "--follow requires --file" in capsys.readouterr().err

    def test_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--demo", "--file", "/no/such/file.log"]) == 2
        assert "file not found" in capsys.readouterr().err

    def test_unknown_format_rejected_by_argparse(self) -> None:
        with pytest.raises(SystemExit):
            build_arg_parser().parse_args(["--format", "csv"])


class TestMissingDatabase:
    def test_friendly_message_and_nonzero_exit(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        exit_code = main(["--json", "--file", str(FIXTURES / "nginx.log")])
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "https://lite.ip2location.com" in err
        assert "IP2LOCATION-LITE-DB11.BIN" in err
        assert "Traceback" not in err

    def test_explicit_bad_path(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(
            ["--json", "--geo-db", "/no/such.BIN", "--file", str(FIXTURES / "nginx.log")]
        )
        assert exit_code == 2
        assert "not found" in capsys.readouterr().err


class TestResolveDbPath:
    def test_cli_flag_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IP2LOCATION_DB", "/env/db.BIN")
        assert resolve_db_path("/cli/db.BIN", "IP2LOCATION_DB", ("IP2LOCATION",)) == Path(
            "/cli/db.BIN"
        )

    def test_env_var_second(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IP2LOCATION_DB", "/env/db.BIN")
        assert resolve_db_path(None, "IP2LOCATION_DB", ("IP2LOCATION",)) == Path("/env/db.BIN")

    def test_data_dir_scan(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        data = tmp_path / "data"
        data.mkdir()
        (data / "IP2LOCATION-LITE-DB11.BIN").write_bytes(b"\x00")
        (data / "IP2PROXY-LITE-PX11.BIN").write_bytes(b"\x00")
        found = resolve_db_path(None, "IP2LOCATION_DB", ("IP2LOCATION",))
        assert found is not None
        assert found.name == "IP2LOCATION-LITE-DB11.BIN"
        found_px = resolve_db_path(None, "IP2PROXY_DB", ("IP2PROXY",))
        assert found_px is not None
        assert found_px.name == "IP2PROXY-LITE-PX11.BIN"

    def test_nothing_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        assert resolve_db_path(None, "IP2LOCATION_DB", ("IP2LOCATION",)) is None


class TestDemoJsonPipeline:
    def read_jsonl(self, out: str) -> list[dict[str, object]]:
        return [json.loads(line) for line in out.strip().splitlines()]

    def test_file_source_emits_valid_jsonl(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--demo", "--json", "--file", str(FIXTURES / "nginx.log")]) == 0
        records = self.read_jsonl(capsys.readouterr().out)
        assert len(records) == 5  # garbage line skipped
        first = records[0]
        assert first["ip"] == "8.8.8.8"
        assert first["country_code"] == "US"
        assert first["is_proxy"] is True
        assert first["ts"] == "2026-07-15T10:00:00+00:00"
        tor = next(r for r in records if r["ip"] == "185.220.101.34")
        assert tor["proxy_type"] == "TOR"

    def test_positional_source(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--demo", "--json", str(FIXTURES / "nginx.log")]) == 0
        assert len(self.read_jsonl(capsys.readouterr().out)) == 5

    def test_sshd_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--demo", "--json", "--format", "sshd", str(FIXTURES / "auth.log")]) == 0
        records = self.read_jsonl(capsys.readouterr().out)
        assert [r["ip"] for r in records] == [
            "45.155.205.233",
            "45.155.205.233",
            "103.152.220.44",
            "196.251.85.10",
        ]

    def test_stdin_default_source(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "sys.stdin", io.StringIO("blocked 8.8.8.8 twice\nblocked 1.1.1.1 once\n")
        )
        assert main(["--demo", "--json"]) == 0
        records = self.read_jsonl(capsys.readouterr().out)
        assert [r["ip"] for r in records] == ["8.8.8.8", "1.1.1.1"]

    def test_json_is_default_when_stdout_is_not_a_tty(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("hit from 8.8.8.8\n"))
        assert main(["--demo"]) == 0  # capsys stdout is not a tty -> JSONL
        records = self.read_jsonl(capsys.readouterr().out)
        assert records[0]["ip"] == "8.8.8.8"

    def test_custom_regex(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        log = tmp_path / "custom.log"
        log.write_text("src=8.8.8.8 action=drop\nsrc=nothing action=allow\n")
        assert main(["--demo", "--json", "--regex", r"src=(?P<ip>\S+)", str(log)]) == 0
        records = self.read_jsonl(capsys.readouterr().out)
        assert [r["ip"] for r in records] == ["8.8.8.8"]


class TestReport:
    def test_report_written_after_stream(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        report = tmp_path / "out"
        report.mkdir()
        report_file = report / "report.html"
        exit_code = main(
            ["--demo", "--json", str(FIXTURES / "nginx.log"), "--report", str(report_file)]
        )
        assert exit_code == 0
        html_text = report_file.read_text(encoding="utf-8")
        assert "8.8.8.8" in html_text
        assert "geotail report" in html_text

    def test_unwritable_report_path(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(
            [
                "--demo",
                "--json",
                "--file",
                str(FIXTURES / "nginx.log"),
                "--report",
                "/no/such/dir/report.html",
            ]
        )
        assert exit_code == 1
        assert "could not write report" in capsys.readouterr().err


class TestEnvironment:
    def test_env_var_points_at_missing_file(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("IP2LOCATION_DB", str(tmp_path / "missing.BIN"))
        assert main(["--json", "--file", str(FIXTURES / "nginx.log")]) == 2
        assert "not found" in capsys.readouterr().err

    def test_environ_is_untouched_after_run(self) -> None:
        before = dict(os.environ)
        main(["--about"])
        assert dict(os.environ) == before
