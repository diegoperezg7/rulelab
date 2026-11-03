"""Command line interface."""

from __future__ import annotations

import json
import signal
import sys
import tempfile
import webbrowser
from importlib import resources
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .analysis import DEFAULT_SESSIONS_PER_MONTH, Analysis, analyze
from .errors import RulelabError
from .experiment import BudgetError, check_budget, execute, load, make_plan, new_results
from .report import VERDICT_LABELS, pp, signed_int, usd, write_report
from .rules import load_rules

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
    help="Find out which lines of your AGENTS.md earn their tokens.",
)
console = Console()
err = Console(stderr=True)

VERDICT_STYLE = {"helps": "green", "hurts": "red", "no_effect": "dim", "inconclusive": "yellow"}


def _fail(message: str, hint: str | None = None, code: int = 1) -> None:
    err.print(f"[bold red]error:[/] {message}")
    if hint:
        err.print(f"[dim]{hint}[/]")
    raise typer.Exit(code)


def _version(value: bool) -> None:
    if value:
        console.print(f"rulelab {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="Show version."),
) -> None:
    pass


@app.command()
def split(
    file: Path = typer.Argument(..., help="AGENTS.md or CLAUDE.md to split.", exists=True, dir_okay=False),
    granularity: str = typer.Option("section", "--granularity", "-g", help="section or bullet."),
    as_json: bool = typer.Option(False, "--json", help="Print rules as JSON."),
) -> None:
    """Show how a file is split into rules (no agent runs)."""
    rf = _load(file, granularity)
    if as_json:
        print(json.dumps([r.to_dict() for r in rf.rules], indent=2, ensure_ascii=False))
        return
    table = Table(title=f"{rf.path}: {len(rf.rules)} rules, ≈{rf.tokens} tokens", title_justify="left")
    table.add_column("id", style="bold")
    table.add_column("rule")
    table.add_column("lines", justify="right")
    table.add_column("≈tok", justify="right")
    for r in rf.rules:
        table.add_row(r.id, r.title, f"{r.start_line}-{r.end_line}", str(r.tokens))
    console.print(table)


def _load(file: Path, granularity: str):
    if granularity not in ("section", "bullet"):
        _fail("--granularity must be 'section' or 'bullet'")
    try:
        return load_rules(file, granularity)  # type: ignore[arg-type]
    except UnicodeDecodeError:
        _fail(f"{file} is not UTF-8 text")


def print_summary(a: Analysis) -> None:
    res = a.results
    full = a.rates.get("full")
    none = a.rates.get("none")
    console.print(
        f"[bold]{res['file']['path']}[/] · model [bold]{res['model']}[/] · "
        f"{len(res['tasks'])} tasks × {res['repeats']} repeats × {len(res['configs'])} configs · "
        f"{len(res['runs'])} runs · {usd(res.get('spent_usd', 0), 4)} USD"
    )
    if full:
        line = f"full file {full[1]}/{full[2]}"
        if none:
            line += f" · no file {none[1]}/{none[2]}"
        if a.whole_file:
            w = a.whole_file
            line += f" · file effect {pp(w.estimate)} pp [{pp(w.low)}, {pp(w.high)}]"
        console.print(line)
    if a.whole_file_tokens and a.whole_file_tokens.n:
        t = a.whole_file_tokens
        console.print(
            f"full file vs no file: {signed_int(t.mean)} input tokens per run "
            f"[{signed_int(t.low)}, {signed_int(t.high)}]"
        )
    table = Table(show_lines=False, title_justify="left")
    table.add_column("rule", overflow="fold")
    table.add_column("≈tok", justify="right")
    table.add_column("effect (pp, 95% CI)", justify="right")
    table.add_column("verdict")
    table.add_column("USD/month", justify="right")
    for r in a.rules:
        e = r.success
        table.add_row(
            f"[bold]{r.id}[/] {r.title}",
            str(r.tokens),
            f"{pp(e.estimate)} [{pp(e.low)}, {pp(e.high)}]",
            f"[{VERDICT_STYLE[e.verdict]}]{VERDICT_LABELS[e.verdict][0]}[/]",
            usd(r.monthly_usd),
        )
    console.print(table)
    console.print(
        f"[dim]USD/month = rule tokens × {a.mean_turns:.1f} model calls/run × {a.sessions_per_month:,} sessions "
        f"at {a.price_in} USD/1M input tokens ({a.price_label}). Tokens ≈ chars/4.[/]"
    )
    if a.floor_or_ceiling == "floor":
        console.print(
            f"[yellow]Floor effect:[/] only {a.overall_rate:.0%} of all runs passed. This model rarely solves these "
            "tasks with or without the file, so success cannot show what a rule does; only the cost columns are "
            "informative. Use a stronger model, more steps or easier tasks."
        )
    elif a.floor_or_ceiling == "ceiling":
        console.print(
            f"[yellow]Ceiling effect:[/] {a.overall_rate:.0%} of all runs passed. The tasks are too easy for this "
            "model to show what a rule does; only the cost columns are informative. Use harder tasks."
        )
    if a.low_power:
        console.print(
            "[yellow]Small sample:[/] most rules are inconclusive. Only large effects can be told apart "
            "from noise with this many tasks and repeats. Add tasks or repeats before deleting a rule."
        )
    if res.get("status") == "budget_exceeded":
        console.print("[yellow]Stopped at --max-cost: results are partial.[/]")
    elif res.get("status") == "interrupted":
        console.print("[yellow]Interrupted: results are partial. Re-run with --resume to continue.[/]")


def _parse_price(price: str | None) -> tuple[float, float] | None:
    if not price:
        return None
    try:
        pin, pout = (float(x) for x in price.split(","))
    except ValueError:
        _fail("--price must look like IN,OUT in USD per million tokens, e.g. 0.30,0.90")
    return (pin, pout)


@app.command()
def run(
    file: Path = typer.Argument(..., help="AGENTS.md or CLAUDE.md to test.", exists=True, dir_okay=False),
    repo: Optional[str] = typer.Option(None, "--repo", help="Git repo (path or URL) to mine tasks from with commitarena."),
    tasks_file: Optional[Path] = typer.Option(None, "--tasks-file", help="Existing tasks.json from `commitarena mine`.", exists=True),
    only: Optional[str] = typer.Option(None, "--only", help="Comma-separated task ids to use (default: all)."),
    max_tasks: int = typer.Option(6, "--max-tasks", min=1, help="Tasks to mine when using --repo."),
    model: str = typer.Option("ollama/qwen3:4b", "--model", "-m", help="provider/model: ollama/qwen3:4b, mistral/codestral-latest, openrouter/<id>, openai/<id>."),
    granularity: str = typer.Option("section", "--granularity", "-g", help="Split by section or bullet."),
    repeats: int = typer.Option(3, "--repeats", "-n", min=1, help="Runs per task and configuration."),
    max_cost: float = typer.Option(1.0, "--max-cost", min=0.0, help="Hard budget in USD. Local models count as 0."),
    inject: str = typer.Option("both", "--inject", help="Where the file goes: both (repo root + system prompt), repo or prompt."),
    max_steps: int = typer.Option(30, "--max-steps", min=1, help="Agent steps (model calls) per run."),
    price: Optional[str] = typer.Option(None, "--price", help="IN,OUT USD per 1M tokens for models without a known price."),
    out: Path = typer.Option(Path("rulelab-results"), "--out", "-o", help="Output directory."),
    resume: bool = typer.Option(False, "--resume", help="Continue an interrupted run in --out."),
    sessions: int = typer.Option(DEFAULT_SESSIONS_PER_MONTH, "--sessions-per-month", help="Agent sessions per month for the cost projection."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the plan and estimate, run nothing."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask for confirmation."),
) -> None:
    """Run the leave-one-out experiment on real tasks from a repository."""
    from . import engine  # imported lazily: needs the commitarena engine

    if inject not in ("both", "repo", "prompt"):
        _fail("--inject must be both, repo or prompt")
    rf = _load(file, granularity)
    if not rf.rules:
        _fail(f"no rules found in {file}")
    try:
        runner = engine.make_runner(
            repo=repo,
            tasks_file=tasks_file,
            model=model,
            cache_dir=out,
            max_tasks=max_tasks,
            context_name=file.name,
            inject=inject,
            max_steps=max_steps,
            price=_parse_price(price),
            check=not dry_run,
        )
        task_list = [t.strip() for t in only.split(",")] if only else None
        plan = make_plan(rf, runner, repeats, task_list)
    except RulelabError as e:
        _fail(str(e), e.hint)
    except ValueError as e:
        _fail(str(e))

    results_path = out / "results.json"
    previous = None
    if resume:
        if not results_path.exists():
            _fail(f"nothing to resume: {results_path} does not exist")
        previous = load(results_path)
        if previous["file"]["text"] != rf.text or previous["model"] != runner.model:
            _fail("--resume needs the same file and model as the interrupted run")
    elif results_path.exists() and not dry_run:
        _fail(f"{results_path} already exists", "Use --resume to continue it or --out to write elsewhere.")

    done = len(previous["runs"]) if previous else 0
    spent = float(previous.get("spent_usd", 0.0)) if previous else 0.0
    console.print(
        f"[bold]{len(rf.rules)} rules[/] → {len(plan.configs)} configurations "
        f"(no file, full file, full minus each rule) × {len(plan.tasks)} tasks × {plan.repeats} repeats "
        f"= [bold]{plan.runs} agent runs[/]" + (f" ({done} already done)" if done else "")
    )
    est = (plan.runs - done) * plan.per_run_usd
    if plan.per_run_usd == 0:
        console.print(f"Estimated cost: [bold]0 USD[/] (local model {runner.model}). Local runs can take a while.")
    else:
        console.print(
            f"Estimated cost: [bold]{est:.2f} USD[/] ({plan.per_run_usd:.4f} USD per run, "
            f"{runner.estimate_note}) · budget --max-cost {max_cost:.2f} USD"
        )
    try:
        check_budget(plan, max_cost, done, spent)
    except BudgetError as e:
        if dry_run:
            console.print(f"[yellow]Over budget:[/] {e}")
            return
        _fail(str(e), "Nothing was run. Lower --repeats, use --only with fewer tasks, pick a cheaper --model, or raise --max-cost.", code=2)
    if dry_run:
        return
    if not yes and plan.per_run_usd > 0 and sys.stdin.isatty():
        typer.confirm(f"Spend up to {min(est, max_cost):.2f} USD?", abort=True)

    results = previous or new_results(rf, plan, runner, max_cost, meta=runner.meta())
    results["max_cost"] = max_cost
    if hasattr(runner, "set_budget"):
        runner.set_budget(max_cost, spent)

    def progress(i: int, total: int, rec: dict) -> None:
        mark = {True: "[green]pass[/]", False: "[red]fail[/]", None: "[yellow]error[/]"}[rec["success"]]
        extra = f"{rec['duration_s']:.0f}s · {rec['input_tokens']:,} tok in · {rec['cost_usd']:.4f} USD"
        console.print(f"[dim]{i:>4}/{total}[/] {rec['config']:<12} {rec['task']:<32} #{rec['repeat']} {mark} [dim]{extra}[/]")

    def _term(signum, frame):  # treat SIGTERM like Ctrl-C: stop cleanly, keep what was measured
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _term)
    try:
        results = execute(plan, runner, results, results_path, max_cost, on_run=progress)
    except RulelabError as e:
        _fail(str(e), e.hint)
    a = analyze(results, sessions_per_month=sessions)
    html = write_report(a, out / "report.html")
    print_summary(a)
    console.print(f"Results: {results_path}\nReport:  {html}")
    if results["status"] == "budget_exceeded":
        raise typer.Exit(2)


@app.command()
def report(
    results_file: Path = typer.Argument(..., help="results.json written by rulelab run.", exists=True, dir_okay=False),
    out: Path = typer.Option(None, "--out", "-o", help="HTML path (default: next to results.json)."),
    sessions: int = typer.Option(DEFAULT_SESSIONS_PER_MONTH, "--sessions-per-month"),
    price_in: Optional[float] = typer.Option(None, "--price-in", help="USD per 1M input tokens for the projection."),
    margin: float = typer.Option(0.10, "--margin", help="± success difference counted as no effect (0.10 = 10 pp)."),
    open_browser: bool = typer.Option(False, "--open", help="Open the report in a browser."),
) -> None:
    """Rebuild the HTML report from a results file."""
    try:
        results = load(results_file)
    except (ValueError, json.JSONDecodeError) as e:
        _fail(str(e))
    a = analyze(results, sessions_per_month=sessions, price_in=price_in, margin=margin)
    html = write_report(a, out or results_file.with_name("report.html"), recorded_note=results.get("recorded"))
    print_summary(a)
    console.print(f"Report: {html}")
    if open_browser:
        webbrowser.open(html.resolve().as_uri())


def demo_results() -> dict:
    """The recorded demo run: packaged in the wheel, or read from examples/ in a clone."""
    try:
        packaged = resources.files("rulelab").joinpath("_demo/results.json")
        if packaged.is_file():
            return json.loads(packaged.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError):
        pass
    repo_copy = Path(__file__).resolve().parents[2] / "examples" / "demo" / "results.json"
    if repo_copy.is_file():
        return json.loads(repo_copy.read_text(encoding="utf-8"))
    _fail("the recorded demo results are missing from this installation")
    raise AssertionError  # unreachable


@app.command()
def demo(
    out: Path = typer.Option(None, "--out", "-o", help="Where to write the HTML report (default: a temp dir)."),
    open_browser: bool = typer.Option(False, "--open", help="Open the report in a browser."),
) -> None:
    """Show a RECORDED real run on the commitarena demo repo. No keys, no Docker."""
    results = demo_results()
    rec = results.get("recorded", {})
    console.print(
        f"[bold magenta]Recorded run[/] · real results from [bold]rulelab run[/] on {rec.get('date', '?')} · "
        f"rulelab {rec.get('version', '?')} · {rec.get('hardware', '?')}. Nothing is executed now."
    )
    a = analyze(results)
    print_summary(a)
    target = out or Path(tempfile.mkdtemp(prefix="rulelab-demo-")) / "report.html"
    html = write_report(a, target, recorded_note=rec)
    console.print(f"Report: {html}")
    if open_browser:
        webbrowser.open(html.resolve().as_uri())


def main() -> None:
    try:
        app()
    except RulelabError as e:  # pragma: no cover - safety net
        err.print(f"[bold red]error:[/] {e}")
        if e.hint:
            err.print(f"[dim]{e.hint}[/]")
        sys.exit(1)
