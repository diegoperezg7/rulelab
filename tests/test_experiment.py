import json

import pytest

from rulelab.analysis import analyze
from rulelab.experiment import BudgetError, check_budget, execute, load, make_plan, new_results
from rulelab.report import render_report
from rulelab.rules import parse_rules
from rulelab.runner import FakeRunner


@pytest.fixture
def rf(sample_text):
    return parse_rules(sample_text, "section")


def test_plan_counts(rf):
    runner = FakeRunner(tasks=["a", "b", "c"])
    plan = make_plan(rf, runner, repeats=3)
    assert [c.id for c in plan.configs][:2] == ["none", "full"]
    assert len(plan.configs) == 2 + len(rf.rules)
    assert plan.runs == len(plan.configs) * 3 * 3
    assert plan.estimated_usd == pytest.approx(plan.runs * 0.01)
    # interleaved: the first block covers every config once
    first = plan.schedule()[: len(plan.configs)]
    assert {c.id for _, _, c in first} == {c.id for c in plan.configs}


def test_no_file_config_has_no_context(rf):
    plan = make_plan(rf, FakeRunner(), repeats=1)
    none = plan.configs[0]
    assert none.context is None
    minus = plan.configs[2]
    assert minus.removed == "R1" and "Guidance for coding agents" not in minus.context


def test_unknown_task(rf):
    with pytest.raises(ValueError, match="unknown task"):
        make_plan(rf, FakeRunner(tasks=["a"]), 1, ["zzz"])


def test_budget_check_message(rf):
    plan = make_plan(rf, FakeRunner(tasks=["a", "b"], cost_per_run=0.05), repeats=3)
    with pytest.raises(BudgetError) as ei:
        check_budget(plan, 1.0)
    msg = str(ei.value)
    assert "needs about 2.10 USD" in msg and "--max-cost 2.10" in msg
    check_budget(plan, 2.10)


def test_execute_full_and_report(rf, tmp_path):
    runner = FakeRunner(tasks=["a", "b"], effects={"pytest -q": 0.4})
    plan = make_plan(rf, runner, repeats=2)
    res = new_results(rf, plan, runner, 10.0)
    out = tmp_path / "results.json"
    res = execute(plan, runner, res, out, max_cost=10.0)
    assert res["status"] == "complete"
    assert len(res["runs"]) == plan.runs
    assert load(out)["runs"] == res["runs"]
    a = analyze(res)
    assert len(a.rules) == len(rf.rules)
    html = render_report(a)
    assert "Repository overview" in html and 'data-lang="en"' in html
    assert "<script" in html and "prefers-color-scheme" in html


def test_execute_stops_at_budget_and_resumes(rf, tmp_path):
    runner = FakeRunner(tasks=["a"], cost_per_run=0.1)
    plan = make_plan(rf, runner, repeats=1)  # 7 configs x 1 task = 7 runs = 0.7 USD
    out = tmp_path / "results.json"
    res = execute(plan, runner, new_results(rf, plan, runner, 0.35), out, max_cost=0.35)
    assert res["status"] == "budget_exceeded"
    assert len(res["runs"]) == 3
    assert res["spent_usd"] == pytest.approx(0.3)
    # resume with a bigger budget runs only what is missing
    res = execute(plan, runner, load(out), out, max_cost=1.0)
    assert res["status"] == "complete"
    assert len(res["runs"]) == 7
    assert len(runner.calls) == 7


def test_infrastructure_errors_are_recorded_and_excluded(rf, tmp_path):
    runner = FakeRunner(tasks=["a", "b"], fail_on={("a", 1)})
    plan = make_plan(rf, runner, repeats=1)
    res = execute(plan, runner, new_results(rf, plan, runner, 5), tmp_path / "r.json", 5)
    errs = [r for r in res["runs"] if r["success"] is None]
    assert len(errs) == len(plan.configs)
    assert analyze(res).errors == len(plan.configs)


def test_results_json_is_serialisable(rf, tmp_path):
    runner = FakeRunner(tasks=["a"])
    plan = make_plan(rf, runner, repeats=1)
    res = new_results(rf, plan, runner, 1)
    json.dumps(res)
    assert res["file"]["rules"][0]["id"] == "R1"


def test_floor_effect_is_flagged(rf, tmp_path):
    runner = FakeRunner(tasks=["a", "b"], base_rate=0.0)
    plan = make_plan(rf, runner, repeats=2)
    res = execute(plan, runner, new_results(rf, plan, runner, 5), tmp_path / "r.json", 5)
    a = analyze(res)
    assert a.floor_or_ceiling == "floor"
    assert all(r.success.verdict == "inconclusive" for r in a.rules)
    assert "Floor effect" in render_report(a)


def test_concurrent_execution_matches_sequential(rf, tmp_path):
    runner = FakeRunner(tasks=["a", "b"], cost_per_run=0.0)
    plan = make_plan(rf, runner, repeats=2)
    res = execute(plan, runner, new_results(rf, plan, runner, 1), tmp_path / "r.json", 1, concurrency=3)
    assert res["status"] == "complete"
    keys = sorted((r["config"], r["task"], r["repeat"]) for r in res["runs"])
    assert keys == sorted((c.id, t, rep) for rep, t, c in plan.schedule())


def test_concurrent_execution_respects_budget(rf, tmp_path):
    runner = FakeRunner(tasks=["a"], cost_per_run=0.1)
    plan = make_plan(rf, runner, repeats=1)  # 7 runs x 0.1
    res = execute(plan, runner, new_results(rf, plan, runner, 0.35), tmp_path / "r.json", 0.35, concurrency=3)
    assert res["status"] == "budget_exceeded"
    assert res["spent_usd"] <= 0.35 + 1e-9
    assert len(res["runs"]) == 3
