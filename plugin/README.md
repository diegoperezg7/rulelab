# rulelab for Claude Code

This plugin adds one skill, `ablate-agent-rules`, that walks Claude through finding out which rules of
your `AGENTS.md` or `CLAUDE.md` actually help your coding agent and what each one costs in tokens.

Ask in plain words, for example "which lines of my CLAUDE.md are worth keeping?". Claude splits the file
into rules, shows the free cost estimate for a leave-one-out experiment on real bug fixes mined from
your repository's git history, and runs it with the open-source
[rulelab](https://github.com/diegoperezg7/rulelab) CLI only after you approve. It then reports, per
rule, the change in success rate with a bootstrap interval, a verdict and its token cost, and says
plainly when the sample is too small to tell.

## What it runs and sends

- It runs `uvx --from git+https://github.com/diegoperezg7/rulelab@v0.1.1 rulelab`, pinned to a release
  tag. Agent-written code runs in a Docker container with no network and CPU, memory and time limits.
- Task descriptions, code context and your rules go only to the model provider you choose (Ollama
  locally, or a provider whose key you set in an environment variable). Keys are never written to files.
- The skill tells Claude to ask before any paid run, and `--max-cost` (1 USD by default) stops the run
  before it spends more. No telemetry.

License: MIT.
