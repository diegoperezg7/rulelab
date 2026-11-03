# Security policy

## Reporting a vulnerability

Please report security issues privately through
[GitHub Security Advisories](https://github.com/diegoperezg7/rulelab/security/advisories/new).
Do not open a public issue. You will get an answer within a week.

## How rulelab handles risk

- Code written by the agent runs only inside Docker containers with **no network**, limited CPU
  (2), memory (2 GB) and time, through the commitarena engine. The model is called from the host.
- API keys are read from environment variables only and are never written to results or reports.
- `--max-cost` (default 1 USD) is checked before every agent run; local models count as 0.
- rulelab sends no telemetry.
