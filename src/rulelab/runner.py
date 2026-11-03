"""The interface rulelab needs from an agent runner, plus a deterministic fake for tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


@dataclass
class RunOutcome:
    success: bool | None  # None = infrastructure error, excluded from statistics
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    turns: int = 0
    duration_s: float = 0.0
    error: str | None = None


class Runner(Protocol):
    """Runs one agent attempt on one task with a given context file (or none)."""

    model: str
    estimate_note: str

    def meta(self) -> dict:
        """Metadata stored with the results (engine, repo, hardware...)."""
        ...

    def task_ids(self) -> list[str]: ...

    def estimate_run_cost(self) -> float:
        """Expected USD for one agent run (0 for local models)."""
        ...

    def run(self, task_id: str, context: str | None, repeat: int) -> RunOutcome: ...


class FakeRunner:
    """Deterministic runner for tests and offline development.

    ``effects`` maps a marker substring to a success-probability shift: if the marker is present
    in the context, the task succeeds more (positive) or less (negative) often.
    """

    def __init__(
        self,
        tasks: list[str] | None = None,
        base_rate: float = 0.5,
        effects: dict[str, float] | None = None,
        cost_per_run: float = 0.01,
        model: str = "fake/model",
        fail_on: set[tuple[str, int]] | None = None,
    ) -> None:
        self.tasks = tasks or [f"task-{i}" for i in range(1, 5)]
        self.base_rate = base_rate
        self.effects = effects or {}
        self.cost_per_run = cost_per_run
        self.model = model
        self.fail_on = fail_on or set()
        self.calls: list[tuple[str, str | None, int]] = []
        self.estimate_note = "fake runner"

    def meta(self) -> dict:
        return {"engine": "fake"}

    def task_ids(self) -> list[str]:
        return list(self.tasks)

    def estimate_run_cost(self) -> float:
        return self.cost_per_run

    def run(self, task_id: str, context: str | None, repeat: int) -> RunOutcome:
        self.calls.append((task_id, context, repeat))
        if (task_id, repeat) in self.fail_on:
            return RunOutcome(None, error="simulated infrastructure error")
        p = self.base_rate
        ctx = context or ""
        for marker, shift in self.effects.items():
            if marker in ctx:
                p += shift
        digest = hashlib.sha256(f"{task_id}|{repeat}|{ctx}".encode()).digest()
        u = int.from_bytes(digest[:8], "big") / 2**64
        ctx_tokens = len(ctx) // 4
        turns = 5
        return RunOutcome(
            success=u < p,
            input_tokens=turns * (2000 + ctx_tokens),
            output_tokens=400,
            cost_usd=self.cost_per_run,
            turns=turns,
            duration_s=0.0,
        )
