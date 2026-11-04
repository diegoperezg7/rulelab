---
name: ablate-agent-rules
description: Find out which rules in an AGENTS.md or CLAUDE.md actually help a coding agent and what each one costs in tokens, with rulelab's leave-one-out experiment on real bug fixes from the repository. Use when the user asks whether their AGENTS.md or CLAUDE.md works, which lines to cut, how much the file costs, or to trim or audit agent instructions.
---

# Audit an AGENTS.md / CLAUDE.md with rulelab

rulelab splits the file into rules and runs the coding agent on real bug-fix tasks mined from the
repository's git history with no file, the full file, and the full file minus each rule. Each rule gets
a success-rate change with a bootstrap interval, a verdict (helps / no effect / hurts / inconclusive),
its tokens and a projected monthly cost.

## Before anything runs

1. Check the tools: `uv --version` and `docker info` must work (agent code runs in a Docker sandbox
   with no network). If Docker is not running, say so and stop.
2. Use this command prefix everywhere (until rulelab is on PyPI):
   `uvx --from git+https://github.com/diegoperezg7/rulelab@v0.1.1 rulelab`
3. To show what a result looks like first, with no keys, no Docker and no cost: `... rulelab demo`.

## Steps

1. **Split, free.** `... rulelab split <file>`. Show the user the rules and their token counts. If a
   rule was split badly (a heading cut from its list, two ideas merged), say so before running.
2. **Plan and estimate, free.** `... rulelab run <file> --repo . --dry-run`. Report the number of
   tasks found, configurations, total agent runs and the cost estimate.
3. **Pick a model.** Ollama (`--model ollama/<model>`) costs nothing but is slow and weak; a paid
   model needs its key in an env var (never print or write it) and `--price in,out` in USD per 1M
   tokens if rulelab does not know the price. Keep `--max-cost` (default 1 USD) and do not start a
   paid run without the user's explicit OK on the estimate.
4. **Run.** `... rulelab run <file> --repo . --model <model> --max-cost <usd>`. Long runs can be
   continued with `--resume`.
5. **Read the report.** For each rule give the verdict, the interval and its tokens. Be explicit that
   with a few tasks most rules come out inconclusive: that is the honest answer, not a failure.
6. **Recommend.** Rules that hurt or cost many tokens with no measurable effect are candidates to
   remove or shorten. Do not edit the user's file unless they ask; if they do, change only what the
   results support and say which numbers back each change.
