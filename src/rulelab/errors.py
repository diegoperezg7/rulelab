"""User-facing errors: printed as one clear line plus a hint, never as a traceback."""

from __future__ import annotations


class RulelabError(Exception):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint
