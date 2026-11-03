"""Experiment configurations: no file, full file, and full file minus each rule."""

from __future__ import annotations

from dataclasses import dataclass

from .rules import RuleFile

NONE = "none"
FULL = "full"


@dataclass(frozen=True)
class Config:
    id: str
    removed: str | None  # rule id removed (leave-one-out), None for "none" / "full"
    context: str | None  # file text given to the agent; None means no file at all

    @property
    def is_ablation(self) -> bool:
        return self.removed is not None


def minus_id(rule_id: str) -> str:
    return f"minus:{rule_id}"


def build_configs(rule_file: RuleFile, include_none: bool = True) -> list[Config]:
    configs: list[Config] = []
    if include_none:
        configs.append(Config(NONE, None, None))
    configs.append(Config(FULL, None, rule_file.render()))
    for rule in rule_file.rules:
        configs.append(Config(minus_id(rule.id), rule.id, rule_file.render({rule.id})))
    return configs


def count_runs(n_configs: int, n_tasks: int, repeats: int) -> int:
    return n_configs * n_tasks * repeats
