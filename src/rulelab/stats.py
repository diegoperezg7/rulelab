"""Effect estimates with bootstrap confidence intervals and per-rule verdicts.

Effect of a rule = success(full file) - success(full file without that rule), averaged over tasks.
Positive means the rule helps. Uncertainty comes from a two-level bootstrap:

1. resample tasks with replacement (task difficulty varies a lot), then
2. for each sampled task, draw each configuration's success rate from its
   Beta(successes + 1/2, failures + 1/2) posterior (Jeffreys prior) instead of
   trusting 3/3 or 0/3 as exact.

Step 2 matters with small samples: plain resampling of 3 identical outcomes gives a
zero-width interval and would turn "we saw nothing" into "no effect".
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Iterable, Literal

Verdict = Literal["helps", "no_effect", "hurts", "inconclusive"]

DEFAULT_MARGIN = 0.10  # +/- 10 percentage points counts as "no effect"
DEFAULT_ITERATIONS = 4000
CONFIDENCE = 0.95


@dataclass
class Cell:
    successes: int = 0
    failures: int = 0

    @property
    def n(self) -> int:
        return self.successes + self.failures

    @property
    def rate(self) -> float:
        return self.successes / self.n if self.n else float("nan")


@dataclass
class Effect:
    estimate: float  # observed mean difference over shared tasks
    low: float
    high: float
    tasks: int
    runs_a: int
    runs_b: int
    verdict: Verdict

    def to_dict(self) -> dict:
        return asdict(self)


def cells(runs: Iterable[dict], config_id: str) -> dict[str, Cell]:
    """Success/failure counts per task for one configuration. Errored runs are skipped."""
    out: dict[str, Cell] = {}
    for r in runs:
        if r["config"] != config_id or r.get("success") is None:
            continue
        c = out.setdefault(r["task"], Cell())
        if r["success"]:
            c.successes += 1
        else:
            c.failures += 1
    return out


def classify(low: float, high: float, margin: float = DEFAULT_MARGIN) -> Verdict:
    if low > 0:
        return "helps"
    if high < 0:
        return "hurts"
    if low >= -margin and high <= margin:
        return "no_effect"
    return "inconclusive"


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def success_effect(
    runs: list[dict],
    config_a: str,
    config_b: str,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    margin: float = DEFAULT_MARGIN,
    seed: int = 0,
) -> Effect:
    """Bootstrap CI for mean_t[p_a(t) - p_b(t)] over tasks run under both configurations."""
    a, b = cells(runs, config_a), cells(runs, config_b)
    tasks = sorted(set(a) & set(b))
    runs_a = sum(a[t].n for t in tasks)
    runs_b = sum(b[t].n for t in tasks)
    if not tasks:
        return Effect(float("nan"), float("nan"), float("nan"), 0, runs_a, runs_b, "inconclusive")
    observed = fmean(a[t].rate - b[t].rate for t in tasks)
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(iterations):
        diffs = []
        for _ in tasks:
            t = tasks[rng.randrange(len(tasks))]
            pa = rng.betavariate(a[t].successes + 0.5, a[t].failures + 0.5)
            pb = rng.betavariate(b[t].successes + 0.5, b[t].failures + 0.5)
            diffs.append(pa - pb)
        draws.append(fmean(diffs))
    draws.sort()
    alpha = (1 - CONFIDENCE) / 2
    low, high = _percentile(draws, alpha), _percentile(draws, 1 - alpha)
    return Effect(observed, low, high, len(tasks), runs_a, runs_b, classify(low, high, margin))


@dataclass
class MeanCI:
    mean: float
    low: float
    high: float
    n: int

    def to_dict(self) -> dict:
        return asdict(self)


def metric_by_task(runs: list[dict], config_id: str, key: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for r in runs:
        if r["config"] != config_id or r.get("success") is None:
            continue
        out.setdefault(r["task"], []).append(float(r.get(key) or 0))
    return out


def metric_delta(
    runs: list[dict],
    config_a: str,
    config_b: str,
    key: str,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int = 0,
) -> MeanCI:
    """Bootstrap CI for the per-run difference of a numeric field (tokens, cost), paired by task."""
    a, b = metric_by_task(runs, config_a, key), metric_by_task(runs, config_b, key)
    tasks = sorted(set(a) & set(b))
    if not tasks:
        return MeanCI(float("nan"), float("nan"), float("nan"), 0)
    observed = fmean(fmean(a[t]) - fmean(b[t]) for t in tasks)
    rng = random.Random(seed)
    draws = []
    for _ in range(iterations):
        diffs = []
        for _ in tasks:
            t = tasks[rng.randrange(len(tasks))]
            xa = [a[t][rng.randrange(len(a[t]))] for _ in a[t]]
            xb = [b[t][rng.randrange(len(b[t]))] for _ in b[t]]
            diffs.append(fmean(xa) - fmean(xb))
        draws.append(fmean(diffs))
    draws.sort()
    alpha = (1 - CONFIDENCE) / 2
    n = sum(len(a[t]) + len(b[t]) for t in tasks)
    return MeanCI(observed, _percentile(draws, alpha), _percentile(draws, 1 - alpha), n)


def success_rate(runs: list[dict], config_id: str) -> tuple[float, int, int]:
    """(rate, successes, valid runs) for one configuration, pooled over tasks."""
    cs = cells(runs, config_id).values()
    s = sum(c.successes for c in cs)
    n = sum(c.n for c in cs)
    return (s / n if n else float("nan"), s, n)
