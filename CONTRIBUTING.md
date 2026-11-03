# Contributing

Thanks for helping. Issues and pull requests are welcome.

## Setup

```bash
git clone https://github.com/diegoperezg7/rulelab && cd rulelab
uv sync
uv run pytest -q
uv run rulelab demo
```

## Ground rules

- Tests never call a paid model. Use `rulelab.runner.FakeRunner` or patch `commitarena.run_task`.
- Tests that need Docker are marked `@pytest.mark.docker`; CI runs them on Linux only.
- Dependencies are pinned with `==` and locked in `uv.lock`.
- Recorded demo data in `examples/` must come from a real `rulelab run`. Never edit numbers by hand.
- The HTML report has no build step: plain HTML, CSS variables and a few lines of JavaScript.
  Keep both languages (EN/ES) and both themes working, and check it at 390 px wide.
- Keep pull requests small and explain how you tested them.
