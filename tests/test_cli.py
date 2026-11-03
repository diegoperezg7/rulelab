import json
import re

import pytest
from typer.testing import CliRunner

from rulelab import cli, engine
from rulelab.errors import RulelabError
from rulelab.runner import FakeRunner

runner = CliRunner()


def plain(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


@pytest.fixture
def agents(tmp_path, sample_text):
    p = tmp_path / "AGENTS.md"
    p.write_text(sample_text)
    return p


def test_split(agents):
    r = runner.invoke(cli.app, ["split", str(agents)])
    assert r.exit_code == 0, r.output
    assert "Repository overview" in r.output
    r = runner.invoke(cli.app, ["split", str(agents), "--granularity", "bullet", "--json"])
    assert r.exit_code == 0
    assert any(x["title"].startswith("Run pytest") for x in json.loads(r.output))


def test_bad_granularity(agents):
    r = runner.invoke(cli.app, ["split", str(agents), "-g", "line"])
    assert r.exit_code == 1
    assert "granularity" in plain(r.output)


def _fake(monkeypatch, **kw):
    fake = FakeRunner(**kw)
    monkeypatch.setattr(engine, "make_runner", lambda **_: fake)
    return fake


def test_run_refuses_over_budget_before_running(monkeypatch, agents, tmp_path):
    fake = _fake(monkeypatch, tasks=["a", "b", "c"], cost_per_run=0.05)
    r = runner.invoke(cli.app, ["run", str(agents), "--repo", str(tmp_path), "--out", str(tmp_path / "o"), "-y"])
    out = plain(r.output)
    assert r.exit_code == 2, out
    assert "63 agent runs" in out
    assert "--max-cost 3.15" in out
    assert fake.calls == []


def test_run_end_to_end(monkeypatch, agents, tmp_path):
    _fake(monkeypatch, tasks=["a", "b"], cost_per_run=0.0)
    o = tmp_path / "o"
    r = runner.invoke(cli.app, ["run", str(agents), "--repo", str(tmp_path), "--out", str(o), "-n", "1"])
    assert r.exit_code == 0, plain(r.output)
    assert (o / "results.json").exists() and (o / "report.html").exists()
    assert "0 USD" in plain(r.output)
    # refuses to overwrite, resume works and runs nothing new
    r = runner.invoke(cli.app, ["run", str(agents), "--repo", str(tmp_path), "--out", str(o), "-n", "1"])
    assert r.exit_code == 1 and "already exists" in plain(r.output)
    r = runner.invoke(cli.app, ["run", str(agents), "--repo", str(tmp_path), "--out", str(o), "-n", "1", "--resume"])
    assert r.exit_code == 0, plain(r.output)


def test_run_dry_run(monkeypatch, agents, tmp_path):
    fake = _fake(monkeypatch, tasks=["a"], cost_per_run=0.01)
    r = runner.invoke(cli.app, ["run", str(agents), "--repo", str(tmp_path), "--dry-run", "--out", str(tmp_path / "o")])
    assert r.exit_code == 0, plain(r.output)
    assert "21 agent runs" in plain(r.output) and fake.calls == []


def test_engine_errors_are_clean(monkeypatch, agents, tmp_path):
    def boom(**_):
        raise RulelabError("Docker is not running", "Start Docker Desktop and retry.")

    monkeypatch.setattr(engine, "make_runner", boom)
    r = runner.invoke(cli.app, ["run", str(agents), "--repo", str(tmp_path)])
    out = plain(r.output)
    assert r.exit_code == 1
    assert "Docker is not running" in out and "Traceback" not in out


def test_report_command(monkeypatch, agents, tmp_path):
    _fake(monkeypatch, tasks=["a"], cost_per_run=0.0)
    o = tmp_path / "o"
    runner.invoke(cli.app, ["run", str(agents), "--repo", str(tmp_path), "--out", str(o), "-n", "1"])
    r = runner.invoke(cli.app, ["report", str(o / "results.json"), "--out", str(tmp_path / "x.html")])
    assert r.exit_code == 0, plain(r.output)
    assert (tmp_path / "x.html").read_text().startswith("<!doctype html>")


def test_report_rejects_other_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}")
    r = runner.invoke(cli.app, ["report", str(p)])
    assert r.exit_code == 1 and "not a rulelab results file" in plain(r.output)
