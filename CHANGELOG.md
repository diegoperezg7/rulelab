# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.2] - 2026-11-04

### Changed
- Published on PyPI as `rulelab-cli` (the name `rulelab` is too close to an existing project). The command is still `rulelab`; `rulelab-cli` works too, so `uvx rulelab-cli` runs it.
- Depends on `commitarena==0.1.1` from PyPI instead of its GitHub tag.

### Added
- Claude Code plugin (`/plugin install rulelab --marketplace diegoperezg7/rulelab`) with the `ablate-agent-rules` skill.

## [0.1.1] - 2026-11-03

### Fixed
- Report: numbers follow the active language (ES `1.953`, `0,23 US$`; EN `1,953`, `0.23 USD`).
- Report: the cost-projection footnote is fully translated.
- Report, terminal summary and docs: the estimated tokens per run (file resent on every call) and the measured
  difference against no file are shown as two separate, named figures.

## [0.1.0] - 2026-11-03

### Added
- `rulelab split`: split AGENTS.md / CLAUDE.md into rules by section or by bullet.
- `rulelab run`: leave-one-out experiment (no file, full file, full file minus each rule) on real
  tasks mined from a repository's history, through the commitarena engine (no-network Docker
  sandbox), 3 repeats by default.
- Per-rule verdict (helps / no effect / hurts / inconclusive) from a two-level bootstrap interval,
  tokens per rule and projected monthly cost.
- Plan and cost estimate before running; `--max-cost` (default 1 USD) checked before every run,
  partial results kept, `--resume` to continue.
- Static HTML report (EN/ES, light/dark, mobile) with the annotated file.
- `--concurrency` to run several agent attempts at once (each in its own sandbox).
- `rulelab demo`: a recorded real run on 4 tasks of the commitarena demo set (ministral-14b, 64 runs).

### Notes
- rulelab depends on `commitarena` from its GitHub tag (`v0.1.1`). PyPI rejects direct URL
  dependencies, so that dependency moves to the PyPI release once commitarena is published there,
  and rulelab is published to PyPI after that.
