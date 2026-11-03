"""Split an AGENTS.md / CLAUDE.md file into rules that can be removed one at a time."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Granularity = Literal["section", "bullet"]

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
_BULLET = re.compile(r"^( {0,1})([-*+]|\d{1,3}[.)])\s+(.*)$")


def approx_tokens(text: str) -> int:
    """Rough token count (characters / 4). Labelled as approximate everywhere it is shown."""
    stripped = text.strip()
    return math.ceil(len(stripped) / 4) if stripped else 0


@dataclass
class Rule:
    id: str
    title: str
    text: str
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive

    @property
    def tokens(self) -> int:
        return approx_tokens(self.text)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "tokens": self.tokens,
        }


@dataclass
class Segment:
    lines: list[str]
    rule_id: str | None  # None = always kept (titles, headings in bullet mode, blank lines)


@dataclass
class RuleFile:
    path: str
    text: str
    granularity: Granularity
    segments: list[Segment] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return approx_tokens(self.text)

    def render(self, without: set[str] | frozenset[str] = frozenset()) -> str:
        """Return the file text with the given rule ids removed."""
        unknown = set(without) - {r.id for r in self.rules}
        if unknown:
            raise ValueError(f"unknown rule id(s): {', '.join(sorted(unknown))}")
        out: list[str] = []
        for seg in self.segments:
            if seg.rule_id is not None and seg.rule_id in without:
                continue
            out.extend(seg.lines)
        text = "\n".join(out)
        text = re.sub(r"\n{3,}", "\n\n", text).strip("\n")
        return text + "\n" if text else ""

    def rule(self, rule_id: str) -> Rule:
        for r in self.rules:
            if r.id == rule_id:
                return r
        raise KeyError(rule_id)


def _code_mask(lines: list[str]) -> list[bool]:
    """True for lines inside (or delimiting) fenced code blocks."""
    mask: list[bool] = []
    fence: str | None = None
    for line in lines:
        m = _FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)
            mask.append(True)
        elif fence is not None:
            mask.append(True)
            if line.strip().startswith(fence):
                fence = None
        else:
            mask.append(False)
    return mask


def _headings(lines: list[str], mask: list[bool]) -> list[tuple[int, int, str]]:
    out = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        m = _HEADING.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip()))
    return out


def _short(text: str, limit: int = 72) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[*_`]", "", text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _split_sections(lines: list[str], mask: list[bool]) -> list[tuple[int, int, str | None]]:
    """Return (start, end_exclusive, title) chunks; title None means fixed preamble."""
    heads = _headings(lines, mask)
    if not heads:
        return [(0, len(lines), "Whole file")]
    levels = [lvl for _, lvl, _ in heads]
    split_level = min(levels)
    # A single top-level title (e.g. "# AGENTS.md") is not a rule: split one level below it.
    if levels.count(split_level) == 1 and heads[0][1] == split_level and len(set(levels)) > 1:
        split_level = min(lvl for lvl in levels if lvl > split_level)
    starts = [(i, t) for i, lvl, t in heads if lvl == split_level]
    chunks: list[tuple[int, int, str | None]] = []
    first = starts[0][0]
    if first > 0:
        pre = lines[:first]
        body = [ln for j, ln in enumerate(pre) if ln.strip() and not _HEADING.match(ln)]
        chunks.append((0, first, "Preamble" if body else None))
    for k, (i, title) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        chunks.append((i, end, title))
    return chunks


def _split_bullets(lines: list[str], mask: list[bool]) -> list[tuple[int, int, str | None]]:
    """Each top-level bullet item (with its nested lines) and each prose paragraph is a rule.

    Headings and blank lines are kept in every configuration.
    """
    chunks: list[tuple[int, int, str | None]] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not mask[i] and (not line.strip() or _HEADING.match(line)):
            chunks.append((i, i + 1, None))
            i += 1
            continue
        start = i
        bullet = None if mask[i] else _BULLET.match(line)
        if bullet:
            title = _short(bullet.group(3))
            i += 1
            while i < n:
                nxt = lines[i]
                if mask[i]:
                    i += 1
                    continue
                if _HEADING.match(nxt) or _BULLET.match(nxt):
                    break
                if not nxt.strip():
                    # a blank line ends the item unless the next non-blank line is indented
                    j = i
                    while j < n and not lines[j].strip():
                        j += 1
                    if j < n and lines[j].startswith((" ", "\t")) and not _BULLET.match(lines[j]):
                        i = j
                        continue
                    break
                i += 1
        else:
            # prose paragraph or code block: runs until a blank line, heading or bullet
            title = None
            while i < n:
                nxt = lines[i]
                if not mask[i] and (not nxt.strip() or _HEADING.match(nxt) or _BULLET.match(nxt)):
                    if i > start:
                        break
                if title is None and not mask[i] and nxt.strip():
                    title = _short(nxt)
                i += 1
            title = title or "Code block"
        chunks.append((start, i, title))
    return chunks


def parse_rules(text: str, granularity: Granularity = "section", path: str = "AGENTS.md") -> RuleFile:
    """Split ``text`` into rules. Every line belongs to exactly one segment."""
    if granularity not in ("section", "bullet"):
        raise ValueError("granularity must be 'section' or 'bullet'")
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    mask = _code_mask(lines)
    chunks = _split_sections(lines, mask) if granularity == "section" else _split_bullets(lines, mask)
    rf = RuleFile(path=path, text=text, granularity=granularity)
    k = 0
    for start, end, title in chunks:
        seg_lines = lines[start:end]
        if title is None or not any(ln.strip() for ln in seg_lines):
            rf.segments.append(Segment(seg_lines, None))
            continue
        k += 1
        rid = f"R{k}"
        body = "\n".join(seg_lines).strip("\n")
        # trailing blank lines are layout, not content
        last = end
        while last > start and not lines[last - 1].strip():
            last -= 1
        rf.rules.append(Rule(rid, title, body, start + 1, last))
        rf.segments.append(Segment(seg_lines, rid))
    return rf


def load_rules(path: str | Path, granularity: Granularity = "section") -> RuleFile:
    p = Path(path)
    return parse_rules(p.read_text(encoding="utf-8"), granularity, path=p.name)
