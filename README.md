<p align="center">
  <img src="docs/assets/banner.svg" alt="rulelab" width="560">
</p>

<p align="center">
  <a href="https://github.com/diegoperezg7/rulelab/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/diegoperezg7/rulelab/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-5d51d1"></a>
  <a href="https://github.com/diegoperezg7/rulelab/releases"><img alt="Release" src="https://img.shields.io/github/v/release/diegoperezg7/rulelab?color=5d51d1"></a>
  <a href="https://github.com/diegoperezg7/rulelab/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/diegoperezg7/rulelab?style=flat&color=5d51d1"></a>
</p>

<p align="center"><b>Find out which lines of your AGENTS.md earn their tokens.</b><br>
Remove one rule at a time and measure success and cost on real tasks.</p>

<p align="center"><a href="README.es.md">Leer en español</a> · <a href="https://diegoperezg7.github.io/rulelab/">Example report</a></p>

<p align="center"><img src="docs/assets/demo.gif" alt="rulelab split and rulelab demo in a terminal" width="820"></p>

<p align="center"><a href="https://diegoperezg7.github.io/rulelab/"><img src="docs/assets/report-light.png" alt="rulelab HTML report" width="820"></a></p>

## Why

Every line in `AGENTS.md` or `CLAUDE.md` is sent to the model on every call. Is it worth it?

The best evidence so far says "often not". Gloaguen et al. (ETH Zurich and LogicStar.ai,
[arXiv 2602.11988](https://arxiv.org/abs/2602.11988)) ran Claude Code, Codex and Qwen Code on
SWE-bench Lite and on CTXbench (138 tasks from 12 repositories) and found that context files
**do not generally improve task success rates** while raising inference cost **by over 20% on
average**:

| Context file | Success | Inference cost |
| --- | --- | --- |
| Written by an LLM | −0.5% (SWE-bench Lite), −2% (CTXbench) | +20%, +23% |
| Written by developers | +2.4% (not significant) | up to +19% |

They also found that repository overviews do not help. That is the average over many repos.
Your file, your repo and your model are what matter to you, and the paper measures whole files,
not the individual rules you would actually delete.

rulelab runs that experiment on **your** repo, **one rule at a time**.

| | What it measures | Tasks |
| --- | --- | --- |
| [fernforge/ruleprof](https://github.com/fernforge/ruleprof) (0★) | Removes rules one at a time; checks whether the agent **obeys** each rule | Toy tasks |
| [sx4im/skillcheck](https://github.com/sx4im/skillcheck) (29★) | Blind A/B test of the **whole file** against no file | Your prompts |
| **rulelab** | Removes rules one at a time; measures **task success and cost** per rule | Real bug fixes from your repo's history, scored by its own tests |

Star counts checked with the GitHub API on 3 Nov 2026.

## Quickstart

See a recorded real run (no API key, no Docker, under a minute):

```bash
uvx --from git+https://github.com/diegoperezg7/rulelab@v0.1.0 rulelab demo --open
```

or from a clone:

```bash
git clone https://github.com/diegoperezg7/rulelab && cd rulelab && uv run rulelab demo --open
```

`uvx rulelab` is coming to PyPI.

Then run it on your own file and repo (needs Docker, and Ollama or an API key):

```bash
rulelab split AGENTS.md                                   # see how the file is split, free
rulelab run AGENTS.md --repo . --dry-run                  # plan and cost estimate, free
rulelab run AGENTS.md --repo . --model ollama/qwen3:4b    # local model, 0 USD
rulelab run AGENTS.md --repo . --model mistral/codestral-latest --max-cost 5
```

## Example output

```text
$ rulelab demo
Recorded run · real results from rulelab run on 2026-11-03 · rulelab 0.1.0 · Darwin arm64 (Apple M4, 16 GB RAM)
AGENTS.md · model mistral/codestral-latest · 6 tasks × 3 repeats × 8 configs · 144 runs · 5.1760 USD
full file 0/18 · no file 0/18 · file effect 0 pp [−17, +17]
full file vs no file: +6,031 input tokens per run [−31,130, +36,229]
 rule                    ≈tok   effect (pp, 95% CI)   verdict        USD/month
 R1 Repository overview    88          0 [−17, +17]   inconclusive        0.35
 R2 Running tests          47          0 [−17, +17]   inconclusive        0.19
 R3 How to fix a bug       56          0 [−17, +16]   inconclusive        0.22
 R4 Lexer and keywords     68          0 [−16, +17]   inconclusive        0.27
 R5 Code style             34         −6 [−24, +15]   inconclusive        0.13
 R6 Communication          30          0 [−17, +17]   inconclusive        0.12
Floor effect: only 1% of all runs passed. [...] only the cost columns are informative.
```

**What this recorded run says, plainly.** The demo is a real `rulelab run` of a 6-rule
[AGENTS.md](examples/demo/AGENTS.md) (it includes a repository overview, as in the paper) on 6
bug-fix tasks mined by commitarena from [sqlparse](https://github.com/andialbrecht/sqlparse)
([tasks.json](examples/demo/tasks.json); 3 of them are also in commitarena's own demo set), with
`mistral/codestral-latest`, 15 agent steps and 3 repeats: 144 agent runs, 5.18 USD.

Codestral solved 1 of 144 attempts. It also solved 0 of 11 in
[commitarena's demo](https://github.com/diegoperezg7/commitarena), so these tasks are simply too hard
for it at 15 steps. With success stuck at the floor, no rule can show an effect on success, and
rulelab says exactly that: every rule is **inconclusive** and the report flags a **floor effect**
instead of inventing a verdict. What the run does measure is cost: the file is ≈328 tokens resent on
each of ~13 model calls per run, about 4,300 input tokens per run that bought no measurable success.
It is the paper's finding (context costs tokens and does not reliably help) reproduced on one repo,
and also the most common outcome you should expect from a small experiment.
To get a verdict on success, run it with a model that solves some but not all of your tasks.

The full report, with the annotated file, is published at
**[diegoperezg7.github.io/rulelab](https://diegoperezg7.github.io/rulelab/)** (EN/ES, light/dark).
Screenshots: [light](docs/assets/report-light.png) · [dark](docs/assets/report-dark.png) ·
[mobile](docs/assets/report-mobile.png).

## How it works

```mermaid
flowchart LR
  F[AGENTS.md / CLAUDE.md] --> S[split into rules<br/>by section or bullet]
  S --> C["configurations:<br/>no file · full file · full minus R1 … Rn"]
  R[your repo] --> M[commitarena mine:<br/>real bug-fix commits with tests]
  C --> X{{each config × each task × 3 repeats}}
  M --> X
  X --> D[Docker sandbox, no network:<br/>agent edits code, model called from host]
  D --> T[repo's own tests decide pass/fail]
  T --> B[bootstrap interval per rule:<br/>helps · no effect · hurts · inconclusive]
  B --> H[HTML report + results.json]
```

1. **Split.** `--granularity section` (default) makes each heading a rule; `bullet` makes each
   top-level bullet or paragraph a rule. A lone `# Title` line is kept in every configuration.
   Check the split with `rulelab split`.
2. **Configurations.** No file, the full file, and the full file without each rule
   (leave-one-out). With *n* rules that is *n* + 2 configurations.
3. **Tasks.** Real bug fixes from your git history, mined by
   [commitarena](https://github.com/diegoperezg7/commitarena): commits that add a test that fails
   before the fix. The agent gets the failing tests, never the commit message.
4. **Runs.** Every configuration runs every task `--repeats` times (default 3) in the same
   no-network Docker sandbox (2 CPU, 2 GB). The file is written at the repo root and appended to
   the system prompt (`--inject both|repo|prompt`). The repo's own AGENTS.md/CLAUDE.md is removed
   first, so "no file" really means none.
5. **Verdict.** Effect of a rule = success with the full file − success without it. The 95%
   interval comes from a two-level bootstrap (tasks resampled; each per-task rate drawn from a
   Beta(s+½, f+½) posterior, so 3/3 vs 3/3 does not look like certainty). **Helps** if the whole
   interval is above 0, **hurts** if below, **no effect** if it fits inside ±10 pp (`--margin`),
   **inconclusive** otherwise.
6. **Cost.** Tokens per rule (≈ characters / 4), the measured input-token difference per run, and
   a monthly projection: rule tokens × model calls per run × sessions per month × input price.

### Read the result honestly

With 6 tasks and 3 repeats, only large effects can be told apart from noise, so **most rules
will come out inconclusive**. The report says so in plain words instead of forcing a verdict.
"Inconclusive" is not "useless": it means this experiment cannot tell. Add tasks (`--max-tasks`)
or repeats before deleting a rule because of it.

## Configuration

| Option | Default | What it does |
| --- | --- | --- |
| `--repo` | | Git repo (path or URL) to mine tasks from |
| `--tasks-file` | | Reuse a `tasks.json` from `commitarena mine` |
| `--only` | all | Comma-separated task ids |
| `--max-tasks` | 6 | Tasks to mine with `--repo` |
| `--model`, `-m` | `ollama/qwen3:4b` | `ollama/…`, `mistral/…`, `openrouter/…`, `openai/…` |
| `--granularity`, `-g` | `section` | `section` or `bullet` |
| `--repeats`, `-n` | 3 | Runs per task and configuration |
| `--max-cost` | 1.0 | Hard budget in USD, checked before every run. Local models count as 0 |
| `--inject` | `both` | Put the file in the repo root, the system prompt, or both |
| `--max-steps` | 30 | Model calls per run |
| `--price` | | `IN,OUT` USD per 1M tokens for models without a known price |
| `--sessions-per-month` | 1000 | For the monthly cost projection |
| `--out`, `-o` | `rulelab-results` | Writes `results.json` (after every run) and `report.html` |
| `--resume` | | Continue an interrupted or budget-stopped run |
| `--dry-run` | | Print the plan and estimate only |

Before anything runs, rulelab prints the number of agent runs and the estimated cost. If the
estimate is over `--max-cost`, it stops and tells you the amount to pass instead. Nothing is spent
until you allow it.

**Small local models.** Ollama serves models with a 4,096-token context by default. An agent run
needs far more, and in our test `qwen3:4b` used up that window thinking and never ran a command.
Start Ollama with a bigger window (for example `OLLAMA_CONTEXT_LENGTH=32768 ollama serve`) before
using a local model.

**Keys** come only from environment variables: `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`,
`OPENAI_API_KEY` (see [.env.example](.env.example)). Ollama needs none (`OLLAMA_HOST` to point
elsewhere). rulelab sends no telemetry.

`rulelab report results.json` rebuilds the report with another `--margin`, `--price-in` or
`--sessions-per-month` without re-running anything.

## Roadmap

Not in v0.1:

- Synthetic tasks for repos without enough bug-fix history.
- Adherence checks (did the agent follow the rule?), as a second signal next to success.
- `.cursor/rules` and skills.
- Rule interactions (removing pairs or groups).
- Automatic rewrites of rules that cost more than they help.
- PyPI release (after commitarena is on PyPI; PyPI does not accept the current GitHub dependency).

## License

[MIT](LICENSE) © 2026 Diego Pérez. The demo tasks come from
[andialbrecht/sqlparse](https://github.com/andialbrecht/sqlparse) (BSD-3-Clause), mined by
commitarena; the demo AGENTS.md in [`examples/demo`](examples/demo) was written for this project.
