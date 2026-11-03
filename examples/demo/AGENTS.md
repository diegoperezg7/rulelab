# AGENTS.md

## Repository overview

sqlparse is a non-validating SQL parser for Python. The package lives in `sqlparse/`:
`lexer.py` and `keywords.py` turn text into tokens, `engine/` groups tokens into statements,
`sql.py` defines the token tree, `filters/` and `formatter.py` implement formatting, and
`cli.py` is the `sqlformat` command. Tests live in `tests/`.

## Running tests

Run the tests that cover your change with `python -m pytest -q tests/<file>.py`, then the whole
suite with `python -m pytest -q`. Do not finish while a test is failing.

## How to fix a bug

Read the failing test first and reproduce the failure before editing anything. Fix the root
cause with the smallest change that makes the test pass. Never edit or delete existing tests to
make them pass.

## Lexer and keywords

Token rules are regular expressions in `sqlparse/keywords.py` and they are tried in order: the
first match wins. When adding or changing a pattern, put more specific patterns before more
general ones and check that neighbouring patterns still match.

## Code style

Follow PEP 8, keep lines under 88 characters, and do not add new dependencies. Keep public
function signatures unchanged.

## Communication

Before finishing, write a short summary of what you changed and why, listing every file you
touched.
