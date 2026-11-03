import math

from rulelab.stats import Cell, classify, metric_delta, success_effect, success_rate


def runs_for(config, task, outcomes, tokens=100):
    return [
        {"config": config, "task": task, "repeat": i + 1, "success": o, "input_tokens": tokens, "cost_usd": 0.01}
        for i, o in enumerate(outcomes)
    ]


def test_classify():
    assert classify(0.05, 0.5) == "helps"
    assert classify(-0.5, -0.01) == "hurts"
    assert classify(-0.05, 0.08) == "no_effect"
    assert classify(-0.3, 0.4) == "inconclusive"


def test_identical_small_samples_are_inconclusive_not_no_effect():
    runs = []
    for t in ("a", "b", "c"):
        runs += runs_for("full", t, [True] * 3) + runs_for("minus:R1", t, [True] * 3)
    e = success_effect(runs, "full", "minus:R1")
    assert e.estimate == 0
    assert e.low < -0.1 and e.high > 0.1
    assert e.verdict == "inconclusive"


def test_large_consistent_effect_is_detected():
    runs = []
    for t in range(12):
        runs += runs_for("full", f"t{t}", [True] * 10) + runs_for("minus:R1", f"t{t}", [False] * 10)
    e = success_effect(runs, "full", "minus:R1")
    assert e.verdict == "helps"
    assert e.estimate == 1.0 and e.low > 0.5


def test_large_sample_no_difference_is_no_effect():
    runs = []
    for t in range(40):
        outs = [True, False] * 15
        runs += runs_for("full", f"t{t}", outs) + runs_for("minus:R1", f"t{t}", outs)
    e = success_effect(runs, "full", "minus:R1")
    assert e.verdict == "no_effect"


def test_errors_are_skipped_and_missing_tasks_handled():
    runs = runs_for("full", "a", [True, None, False]) + runs_for("minus:R1", "b", [True])
    e = success_effect(runs, "full", "minus:R1")
    assert e.tasks == 0 and e.verdict == "inconclusive" and math.isnan(e.estimate)
    assert success_rate(runs, "full") == (0.5, 1, 2)


def test_deterministic_with_seed():
    runs = runs_for("full", "a", [True, False, True]) + runs_for("minus:R1", "a", [False, False, True])
    assert success_effect(runs, "full", "minus:R1", seed=3) == success_effect(runs, "full", "minus:R1", seed=3)


def test_metric_delta():
    runs = runs_for("full", "a", [True] * 3, tokens=500) + runs_for("minus:R1", "a", [True] * 3, tokens=400)
    d = metric_delta(runs, "full", "minus:R1", "input_tokens")
    assert d.mean == 100 and d.low == 100 and d.high == 100


def test_cell():
    c = Cell(2, 1)
    assert c.n == 3 and abs(c.rate - 2 / 3) < 1e-9
