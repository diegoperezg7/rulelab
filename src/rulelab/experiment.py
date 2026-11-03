"""Run the leave-one-out experiment under a hard budget and persist results as JSON."""

from __future__ import annotations

import json
import math
import platform
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import __version__
from .configs import Config, build_configs, count_runs
from .rules import RuleFile
from .runner import RunOutcome, Runner

SCHEMA = 1


class BudgetError(Exception):
    """The experiment would cost more than --max-cost."""

    def __init__(self, needed: float, max_cost: float, runs: int, per_run: float) -> None:
        self.needed, self.max_cost, self.runs, self.per_run = needed, max_cost, runs, per_run
        self.suggested = math.ceil(round(needed * 100, 6)) / 100
        super().__init__(
            f"This experiment needs about {self.suggested:.2f} USD ({runs} agent runs x {per_run:.4f} USD) "
            f"but --max-cost is {max_cost:.2f} USD. Re-run with --max-cost {self.suggested:.2f} to allow it."
        )


@dataclass
class Plan:
    configs: list[Config]
    tasks: list[str]
    repeats: int
    per_run_usd: float

    @property
    def runs(self) -> int:
        return count_runs(len(self.configs), len(self.tasks), self.repeats)

    @property
    def estimated_usd(self) -> float:
        return self.runs * self.per_run_usd

    def schedule(self) -> list[tuple[int, str, Config]]:
        """Interleaved order (repeat > task > config) so a partial run stays balanced."""
        return [
            (rep, task, cfg)
            for rep in range(1, self.repeats + 1)
            for task in self.tasks
            for cfg in self.configs
        ]


def make_plan(rule_file: RuleFile, runner: Runner, repeats: int, tasks: list[str] | None = None) -> Plan:
    if repeats < 1:
        raise ValueError("--repeats must be at least 1")
    if not rule_file.rules:
        raise ValueError("no rules found in the file: nothing to ablate")
    available = runner.task_ids()
    if tasks:
        missing = [t for t in tasks if t not in available]
        if missing:
            raise ValueError(f"unknown task(s): {', '.join(missing)}. Available: {', '.join(available)}")
        chosen = list(tasks)
    else:
        chosen = available
    if not chosen:
        raise ValueError("the runner has no tasks")
    return Plan(build_configs(rule_file), chosen, repeats, runner.estimate_run_cost())


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_results(rule_file: RuleFile, plan: Plan, runner: Runner, max_cost: float, meta: dict | None = None) -> dict:
    return {
        "schema": SCHEMA,
        "tool": "rulelab",
        "version": __version__,
        "created": _now(),
        "finished": None,
        "status": "running",
        "model": runner.model,
        "meta": {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            **(meta or {}),
        },
        "file": {
            "path": rule_file.path,
            "granularity": rule_file.granularity,
            "text": rule_file.text,
            "tokens": rule_file.tokens,
            "rules": [r.to_dict() for r in rule_file.rules],
        },
        "configs": [{"id": c.id, "removed": c.removed} for c in plan.configs],
        "tasks": plan.tasks,
        "repeats": plan.repeats,
        "max_cost": max_cost,
        "estimated_usd": plan.estimated_usd,
        "spent_usd": 0.0,
        "runs": [],
    }


def save(results: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("tool") != "rulelab" or "runs" not in data:
        raise ValueError(f"{path} is not a rulelab results file")
    return data


def execute(
    plan: Plan,
    runner: Runner,
    results: dict,
    out: Path,
    max_cost: float,
    on_run: Callable[[int, int, dict], None] | None = None,
    concurrency: int = 1,
) -> dict:
    """Run every scheduled attempt not already in ``results`` (so it can resume).

    Up to ``concurrency`` attempts run at once. Before starting each one, the measured spend plus
    the expected cost of every attempt in flight (and this one) is checked against ``max_cost``;
    if it does not fit, no new attempts start, the ones in flight finish, and the experiment ends
    with status ``budget_exceeded``. Everything measured is saved after each attempt.
    """
    done = {(r["config"], r["task"], r["repeat"]) for r in results["runs"]}
    schedule = plan.schedule()
    total = len(schedule)
    todo = [(i, rep, task, cfg) for i, (rep, task, cfg) in enumerate(schedule, start=1) if (cfg.id, task, rep) not in done]
    spent = float(results.get("spent_usd", 0.0))
    results["status"] = "running"
    stop: str | None = None
    finished = 0
    pool = ThreadPoolExecutor(max_workers=max(1, concurrency))
    in_flight: dict = {}
    queue = list(todo)
    try:
        while queue or in_flight:
            while queue and stop is None and len(in_flight) < max(1, concurrency):
                if spent + (len(in_flight) + 1) * plan.per_run_usd > max_cost + 1e-12:
                    stop = "budget_exceeded"
                    break
                i, rep, task, cfg = queue.pop(0)
                in_flight[pool.submit(runner.run, task, cfg.context, rep)] = (i, rep, task, cfg)
            if not in_flight:
                break
            ready, _ = wait(list(in_flight), return_when=FIRST_COMPLETED)
            for fut in ready:
                i, rep, task, cfg = in_flight.pop(fut)
                outcome: RunOutcome = fut.result()
                spent += outcome.cost_usd
                if outcome.error == "budget_exceeded":
                    stop = "budget_exceeded"
                    results["spent_usd"] = round(spent, 6)
                    continue
                record = {"config": cfg.id, "task": task, "repeat": rep, **asdict(outcome)}
                results["runs"].append(record)
                results["spent_usd"] = round(spent, 6)
                save(results, out)
                finished += 1
                if on_run:
                    on_run(len(done) + finished, total, record)
        results["status"] = stop or ("complete" if not queue else "interrupted")
    except KeyboardInterrupt:
        results["status"] = "interrupted"
        pool.shutdown(wait=False, cancel_futures=True)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    results["finished"] = _now()
    save(results, out)
    return results


def check_budget(plan: Plan, max_cost: float, done_runs: int = 0, already_spent: float = 0.0) -> None:
    """Refuse to start when the whole experiment cannot fit in ``max_cost``."""
    remaining_runs = max(plan.runs - done_runs, 0)
    needed = remaining_runs * plan.per_run_usd + already_spent
    if needed > max_cost + 1e-12:
        raise BudgetError(needed, max_cost, remaining_runs, plan.per_run_usd)
