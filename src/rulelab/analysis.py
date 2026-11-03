"""Turn raw runs into per-rule verdicts, token counts and projected monthly cost."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from .configs import FULL, NONE, minus_id
from .stats import DEFAULT_MARGIN, Effect, MeanCI, metric_delta, success_effect, success_rate

# Reference price used to project monthly cost when the measured model is local (free).
# Claude Sonnet 5.5 input list price on OpenRouter, checked 3 Nov 2026 (USD per 1M tokens).
REFERENCE_PRICE_IN = 2.0
REFERENCE_PRICE_LABEL = "Claude Sonnet 5.5 input price on OpenRouter (3 Nov 2026)"
DEFAULT_SESSIONS_PER_MONTH = 1000


@dataclass
class RuleResult:
    id: str
    title: str
    text: str
    start_line: int
    end_line: int
    tokens: int  # approximate tokens in the rule text
    success: Effect  # full - minus(rule): positive = removing the rule loses success
    input_tokens: MeanCI  # full - minus(rule), per run
    cost: MeanCI  # full - minus(rule), USD per run
    tokens_per_run: float  # rule tokens x mean model calls per run (the file is resent each call)
    monthly_usd: float  # projected cost of carrying the rule

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k not in ("success", "input_tokens", "cost")}
        d["success"] = self.success.to_dict()
        d["input_tokens"] = self.input_tokens.to_dict()
        d["cost"] = self.cost.to_dict()
        return d


@dataclass
class Analysis:
    results: dict
    rules: list[RuleResult]
    whole_file: Effect | None  # full - none
    whole_file_tokens: MeanCI | None
    rates: dict[str, tuple[float, int, int]]
    mean_turns: float
    price_in: float
    price_label: str
    sessions_per_month: int
    margin: float
    errors: int
    counts: dict[str, int]

    @property
    def verdict_counts(self) -> dict[str, int]:
        out = {"helps": 0, "no_effect": 0, "hurts": 0, "inconclusive": 0}
        for r in self.rules:
            out[r.success.verdict] += 1
        return out

    @property
    def low_power(self) -> bool:
        return self.verdict_counts["inconclusive"] >= max(1, len(self.rules) // 2)


def _model_price_in(results: dict) -> float:
    return float(results.get("meta", {}).get("price_in_per_mtok") or 0.0)


def analyze(
    results: dict,
    *,
    sessions_per_month: int = DEFAULT_SESSIONS_PER_MONTH,
    price_in: float | None = None,
    margin: float = DEFAULT_MARGIN,
    seed: int = 0,
) -> Analysis:
    runs = results["runs"]
    config_ids = [c["id"] for c in results["configs"]]
    valid = [r for r in runs if r.get("success") is not None]
    errors = len(runs) - len(valid)

    full_turns = [r.get("turns") or 0 for r in valid if r["config"] == FULL]
    mean_turns = fmean(full_turns) if full_turns else 0.0

    if price_in is None:
        model_price = _model_price_in(results)
        if model_price > 0:
            price_in, price_label = model_price, f"{results.get('model')} input price"
        else:
            price_in, price_label = REFERENCE_PRICE_IN, REFERENCE_PRICE_LABEL
    else:
        price_label = "--price-in"

    rules: list[RuleResult] = []
    for i, rd in enumerate(results["file"]["rules"]):
        cid = minus_id(rd["id"])
        if cid not in config_ids:
            continue
        eff = success_effect(runs, FULL, cid, margin=margin, seed=seed + i)
        tok = metric_delta(runs, FULL, cid, "input_tokens", seed=seed + i)
        cost = metric_delta(runs, FULL, cid, "cost_usd", seed=seed + i)
        per_run = rd["tokens"] * mean_turns
        rules.append(
            RuleResult(
                id=rd["id"],
                title=rd["title"],
                text=rd["text"],
                start_line=rd["start_line"],
                end_line=rd["end_line"],
                tokens=rd["tokens"],
                success=eff,
                input_tokens=tok,
                cost=cost,
                tokens_per_run=per_run,
                monthly_usd=per_run * sessions_per_month * price_in / 1_000_000,
            )
        )

    whole = whole_tok = None
    if NONE in config_ids:
        whole = success_effect(runs, FULL, NONE, margin=margin, seed=seed + 999)
        whole_tok = metric_delta(runs, FULL, NONE, "input_tokens", seed=seed + 999)

    rates = {cid: success_rate(runs, cid) for cid in config_ids}
    counts = {cid: sum(1 for r in runs if r["config"] == cid) for cid in config_ids}
    return Analysis(
        results=results,
        rules=rules,
        whole_file=whole,
        whole_file_tokens=whole_tok,
        rates=rates,
        mean_turns=mean_turns,
        price_in=price_in,
        price_label=price_label,
        sessions_per_month=sessions_per_month,
        margin=margin,
        errors=errors,
        counts=counts,
    )


def file_monthly_usd(a: Analysis) -> float:
    tokens = a.results["file"]["tokens"]
    return tokens * a.mean_turns * a.sessions_per_month * a.price_in / 1_000_000
