"""Adapter between rulelab and the commitarena engine (tasks, no-network sandbox, agent loop)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from .errors import RulelabError
from .runner import RunOutcome

# Assumed tokens for one agent run when estimating cost before anything has run
# (same assumption as the project plan: ~300k input, ~10k output per agent task).
EST_TOKENS_IN = 300_000
EST_TOKENS_OUT = 10_000


def _ca():
    try:
        import commitarena
    except ImportError as e:  # pragma: no cover - dependency is declared
        raise RulelabError(
            "the commitarena engine is not installed",
            "Reinstall rulelab: uvx --from git+https://github.com/diegoperezg7/rulelab rulelab",
        ) from e
    return commitarena


def hardware() -> str:
    mem = ""
    try:
        if platform.system() == "Darwin":
            b = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
            chip = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
            ).stdout.strip()
            mem = f"{chip}, {b // 2**30} GB RAM"
        elif Path("/proc/meminfo").exists():
            kb = int(Path("/proc/meminfo").read_text().split()[1])
            mem = f"{kb // 2**20} GB RAM"
    except Exception:  # noqa: BLE001 - best effort only
        pass
    return f"{platform.system()} {platform.machine()}" + (f" ({mem})" if mem else "")


def _ollama_host() -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    return host.replace("://0.0.0.0", "://localhost", 1)


def check_model(spec) -> None:
    """Fail early with a clear message: missing key, Ollama down, or model not pulled."""
    ca = _ca()
    from commitarena.llm import PROVIDERS  # provider -> (base_url, env var)

    if spec.is_local:
        host = _ollama_host()
        try:
            with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as r:
                names = {m.get("name") for m in json.load(r).get("models", [])}
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise RulelabError(
                f"cannot reach Ollama at {host}",
                "Start it with `ollama serve` (or the Ollama app), or set OLLAMA_HOST.",
            ) from e
        wanted = spec.name if ":" in spec.name else f"{spec.name}:latest"
        if wanted not in names and spec.name not in names:
            raise RulelabError(
                f"model '{spec.name}' is not available in Ollama",
                f"Pull it with `ollama pull {spec.name}`. Installed: {', '.join(sorted(n for n in names if n)) or 'none'}.",
            )
        return
    env = PROVIDERS[spec.provider][1]
    if env and not os.environ.get(env):
        raise RulelabError(
            f"missing API key for provider '{spec.provider}'",
            f"Set the {env} environment variable, or use a local model such as ollama/qwen3:4b.",
        )
    if spec.unit_price() is None and spec.provider != "openrouter":
        raise RulelabError(
            f"no price known for {spec.id}, so the budget cannot be enforced",
            "Pass --price IN,OUT (USD per million input/output tokens).",
        )
    del ca


def check_docker() -> None:
    ca = _ca()
    if shutil.which("docker") is None:
        raise RulelabError("Docker is not installed", "Install Docker Desktop (or Docker Engine) and start it.")
    try:
        ca.ensure_docker()
    except ca.CommitArenaError as e:
        raise RulelabError(str(e)) from e


class CommitarenaRunner:
    """Runs one agent attempt per call through commitarena's ``run_task``."""

    def __init__(
        self,
        tasks: list,
        model: str,
        *,
        context_name: str = "AGENTS.md",
        inject: str = "both",
        max_steps: int = 30,
        price: tuple[float, float] | None = None,
        tasks_source: str = "",
    ) -> None:
        ca = _ca()
        try:
            self.spec = ca.ModelSpec.parse(model, price=price)
        except ca.CommitArenaError as e:
            raise RulelabError(str(e)) from e
        self.model = self.spec.id
        self.tasks = {t.id: t for t in tasks}
        self.context_name = context_name
        self.inject = inject
        self.max_steps = max_steps
        self.tasks_source = tasks_source
        self.budget = ca.Budget(max_cost=float("inf"))
        pin, pout = self.spec.unit_price() or (0.0, 0.0)
        self.price = (pin, pout)
        self.estimate_note = (
            f"assumes ~{EST_TOKENS_IN // 1000}k input + {EST_TOKENS_OUT // 1000}k output tokens per run "
            f"at {pin}/{pout} USD per 1M"
        )

    def set_budget(self, max_cost: float, spent: float = 0.0) -> None:
        self.budget.max_cost = max_cost
        self.budget.spent = spent

    def meta(self) -> dict:
        ca = _ca()
        return {
            "engine": f"commitarena {ca.__version__}",
            "tasks_source": self.tasks_source,
            "inject": self.inject,
            "max_steps": self.max_steps,
            "hardware": hardware(),
            "price_in_per_mtok": self.price[0],
            "price_out_per_mtok": self.price[1],
            "task_info": {
                tid: {"repo": str(t.repo), "commit": t.commit, "date": t.date} for tid, t in self.tasks.items()
            },
        }

    def task_ids(self) -> list[str]:
        return list(self.tasks)

    def estimate_run_cost(self) -> float:
        if self.spec.is_local:
            return 0.0
        pin, pout = self.price
        return (EST_TOKENS_IN * pin + EST_TOKENS_OUT * pout) / 1_000_000

    def run(self, task_id: str, context: str | None, repeat: int) -> RunOutcome:
        ca = _ca()
        ctx = None
        if context is not None:
            ctx = ca.ContextFile(
                content=context,
                name=self.context_name,
                in_repo=self.inject in ("both", "repo"),
                in_prompt=self.inject in ("both", "prompt"),
            )
        try:
            res = ca.run_task(
                self.tasks[task_id],
                self.spec,
                budget=self.budget,
                context=ctx,
                strip_context_files=True,
                agent_config=ca.AgentConfig(max_steps=self.max_steps),
                sandbox_config=ca.SandboxConfig(cpus=2, memory="2g"),
            )
        except ca.BudgetExceeded:
            return RunOutcome(None, error="budget_exceeded")
        except (ca.MissingAPIKey, ca.DockerUnavailable, ca.ModelUnavailable) as e:
            raise RulelabError(str(e)) from e
        except ca.CommitArenaError as e:
            return RunOutcome(None, error=str(e)[:500])
        infra = res.stop_reason in ("model_error", "budget_exceeded") or (res.error and not res.steps)
        return RunOutcome(
            success=None if infra else bool(res.passed),
            input_tokens=res.tokens_in,
            output_tokens=res.tokens_out,
            cost_usd=res.cost_usd,
            turns=res.steps,
            duration_s=res.wall_time_s,
            error=(res.stop_reason if res.stop_reason == "budget_exceeded" else (res.error or None)),
        )


def load_task_list(tasks_file: Path | None, repo: str | None, cache_dir: Path, max_tasks: int) -> tuple[list, str]:
    """Tasks from an existing tasks.json, or mined from ``repo`` with commitarena (cached)."""
    ca = _ca()
    try:
        if tasks_file is not None:
            return ca.load_tasks(str(tasks_file)), str(tasks_file)
        if repo is None:
            raise RulelabError("pass --repo or --tasks-file", "--repo mines tasks from git history with commitarena.")
        cached = cache_dir / "tasks.json"
        if cached.exists():
            return ca.load_tasks(str(cached)), str(repo)
        from commitarena.mine import mine

        cache_dir.mkdir(parents=True, exist_ok=True)
        tasks, _meta = mine(repo, out=cached, max_tasks=max_tasks)
        return tasks, str(repo)
    except ca.CommitArenaError as e:
        raise RulelabError(str(e)) from e


def make_runner(
    *,
    repo: str | None = None,
    tasks_file: Path | None = None,
    model: str,
    cache_dir: Path = Path("rulelab-results"),
    max_tasks: int = 6,
    context_name: str = "AGENTS.md",
    inject: str = "both",
    max_steps: int = 30,
    price: tuple[float, float] | None = None,
    check: bool = True,
) -> CommitarenaRunner:
    runner_probe = CommitarenaRunner([], model, price=price)  # validates the model id early
    if check:
        check_model(runner_probe.spec)
        check_docker()
    tasks, source = load_task_list(tasks_file, repo, cache_dir, max_tasks)
    if not tasks:
        raise RulelabError("no tasks found", "Mine more commits (--max-tasks) or pass another --tasks-file.")
    return CommitarenaRunner(
        tasks, model, context_name=context_name, inject=inject, max_steps=max_steps, price=price, tasks_source=source
    )
