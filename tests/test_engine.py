"""Adapter tests with commitarena's run_task replaced: no Docker, no model calls."""

import pytest

import commitarena
from rulelab import engine
from rulelab.errors import RulelabError


class FakeTask:
    def __init__(self, tid):
        self.id, self.repo, self.commit, self.date = tid, "https://example.com/r.git", "abc", "2026-01-01"


def make(monkeypatch, result=None, exc=None):
    calls = []

    def fake_run_task(task, spec, **kw):
        calls.append((task.id, kw))
        if exc:
            raise exc
        return result

    monkeypatch.setattr(commitarena, "run_task", fake_run_task)
    return engine.CommitarenaRunner([FakeTask("t1")], "ollama/qwen3:4b", context_name="CLAUDE.md"), calls


def rr(**kw):
    base = dict(task_id="t1", model="ollama/qwen3:4b", passed=True, tokens_in=1000, tokens_out=50, steps=4,
                cost_usd=0.0, wall_time_s=3.0, stop_reason="finished")
    base.update(kw)
    return commitarena.RunResult(**base)


def test_maps_result_and_context(monkeypatch):
    runner, calls = make(monkeypatch, rr())
    out = runner.run("t1", "# rules\n", 1)
    assert out.success is True and out.turns == 4 and out.input_tokens == 1000
    kw = calls[0][1]
    assert kw["strip_context_files"] is True
    assert kw["context"].name == "CLAUDE.md" and kw["context"].in_repo and kw["context"].in_prompt
    runner.run("t1", None, 2)
    assert calls[1][1]["context"] is None


def test_model_error_is_excluded(monkeypatch):
    runner, _ = make(monkeypatch, rr(passed=False, stop_reason="model_error", error="boom", steps=1))
    assert runner.run("t1", "x", 1).success is None


def test_budget_exceeded(monkeypatch):
    runner, _ = make(monkeypatch, exc=commitarena.BudgetExceeded(1.0, 1.0))
    assert runner.run("t1", "x", 1).error == "budget_exceeded"


def test_fatal_errors_become_rulelab_errors(monkeypatch):
    runner, _ = make(monkeypatch, exc=commitarena.DockerUnavailable("Docker is not running"))
    with pytest.raises(RulelabError, match="Docker"):
        runner.run("t1", "x", 1)


def test_estimates():
    local = engine.CommitarenaRunner([], "ollama/qwen3:4b")
    assert local.estimate_run_cost() == 0
    paid = engine.CommitarenaRunner([], "mistral/codestral-latest")
    assert paid.estimate_run_cost() == pytest.approx((300_000 * 0.30 + 10_000 * 0.90) / 1e6)
    assert paid.meta()["price_in_per_mtok"] == 0.30


def test_missing_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    spec = commitarena.ModelSpec.parse("mistral/codestral-latest")
    with pytest.raises(RulelabError, match="missing API key"):
        engine.check_model(spec)


def test_ollama_unreachable(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    with pytest.raises(RulelabError, match="cannot reach Ollama"):
        engine.check_model(commitarena.ModelSpec.parse("ollama/qwen3:4b"))


def test_bad_provider():
    with pytest.raises(RulelabError, match="Unknown provider"):
        engine.CommitarenaRunner([], "nope/x")
