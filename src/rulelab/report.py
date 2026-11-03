"""Static HTML report (ES/EN, light/dark, mobile) with the annotated rules file."""

from __future__ import annotations

import math
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup, escape

from . import __version__
from .analysis import Analysis, file_monthly_usd, file_tokens_per_run
from .configs import FULL, NONE

VERDICT_LABELS = {
    "helps": ("helps", "ayuda"),
    "no_effect": ("no effect", "sin efecto"),
    "hurts": ("hurts", "empeora"),
    "inconclusive": ("inconclusive", "no concluyente"),
}

PLURAL_ES = {"helps": "ayudan", "no_effect": "sin efecto", "hurts": "empeoran", "inconclusive": "no concluyentes"}


def _num(x: float) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def pp(x: float | None, signed: bool = True) -> str:
    if x is None or not _num(x):
        return "n/a"
    v = round(x * 100)
    if v == 0:
        return "0"
    s = f"{v:+d}" if signed else f"{v:d}"
    return s.replace("-", "−")


def pct(x: float | None) -> str:
    if x is None or not _num(x):
        return "n/a"
    return f"{round(x * 100)}%"


def signed_int(x: float | None) -> str:
    if x is None or not _num(x):
        return "n/a"
    v = round(x)
    return (f"{v:+,d}" if v else "0").replace("-", "−")


def usd(x: float | None, digits: int = 2) -> str:
    if x is None or not _num(x):
        return "n/a"
    if 0 < abs(x) < 10 ** (-digits):
        return f"<{10 ** (-digits):.{digits}f}"
    return f"{x:,.{digits}f}"


def _es(text: str) -> str:
    """English-formatted number -> Spanish (1,953.5 -> 1.953,5)."""
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _both(en: str, es: str) -> Markup:
    return Markup('<span lang="en">%s</span><span lang="es">%s</span>') % (escape(en), escape(es))


def b_num(x: float | None, digits: int = 0) -> Markup:
    if x is None or not _num(x):
        return _both("n/a", "n/d")
    en = f"{x:,.{digits}f}"
    return _both(en, _es(en))


def b_signed_int(x: float | None) -> Markup:
    en = signed_int(x)
    return _both(en, "n/d" if en == "n/a" else _es(en))


def b_usd(x: float | None, digits: int = 2) -> Markup:
    en = usd(x, digits)
    if en == "n/a":
        return _both("n/a", "n/d")
    return _both(f"{en} USD", f"{_es(en)} US$")


def b_pct(x: float | None) -> Markup:
    en = pct(x)
    return _both(en, "n/d" if en == "n/a" else en.replace("%", "\u00a0%"))


def b_plain(x) -> Markup:
    en = str(x)
    return _both(en, _es(en))


def ci_bar(low: float, high: float, est: float, margin: float, width: int = 168) -> dict:
    """Geometry for the interval glyph on a fixed -100..+100 pp axis."""
    if not (_num(low) and _num(high)):
        return {"ok": False}

    def x(v: float) -> float:
        v = max(-1.0, min(1.0, v))
        return round((v + 1) / 2 * width, 1)

    return {
        "ok": True,
        "w": width,
        "x0": x(low),
        "x1": x(high),
        "xe": x(est) if _num(est) else None,
        "z": x(0),
        "m0": x(-margin),
        "m1": x(margin),
    }


def _annotated(a: Analysis) -> list[dict]:
    """Split the original file into blocks: fixed lines and rule blocks with their result."""
    lines = a.results["file"]["text"].replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    by_start = {r.start_line: r for r in a.rules}
    blocks: list[dict] = []
    i = 1
    fixed: list[str] = []
    while i <= len(lines):
        r = by_start.get(i)
        if r:
            if fixed:
                blocks.append({"rule": None, "text": "\n".join(fixed)})
                fixed = []
            blocks.append({"rule": r, "text": "\n".join(lines[r.start_line - 1 : r.end_line])})
            i = r.end_line + 1
        else:
            fixed.append(lines[i - 1])
            i += 1
    if fixed:
        blocks.append({"rule": None, "text": "\n".join(fixed)})
    # drop empty fixed blocks made only of blank lines between rules
    return [b for b in blocks if b["rule"] or b["text"].strip()]


def render_report(a: Analysis, *, recorded_note: dict | None = None) -> str:
    env = Environment(
        loader=PackageLoader("rulelab", "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(pp=pp, pct=b_pct, usd=b_usd, signed_int=b_signed_int, num=b_num, plain=b_plain)
    res = a.results
    configs = []
    for c in res["configs"]:
        rate, s, n = a.rates[c["id"]]
        runs = [r for r in res["runs"] if r["config"] == c["id"] and r.get("success") is not None]
        configs.append(
            {
                "id": c["id"],
                "removed": c["removed"],
                "rate": rate,
                "s": s,
                "n": n,
                "planned": len(res["tasks"]) * res["repeats"],
                "tokens": (sum(r["input_tokens"] for r in runs) / len(runs)) if runs else float("nan"),
                "cost": (sum(r["cost_usd"] for r in runs) / len(runs)) if runs else float("nan"),
            }
        )
    rules = [
        {
            "r": r,
            "bar": ci_bar(r.success.low, r.success.high, r.success.estimate, a.margin),
            "share": r.tokens / res["file"]["tokens"] if res["file"]["tokens"] else 0,
        }
        for r in a.rules
    ]
    template = env.get_template("report.html.j2")
    return template.render(
        a=a,
        res=res,
        rules=rules,
        configs=configs,
        blocks=_annotated(a),
        verdicts=VERDICT_LABELS,
        plural_es=PLURAL_ES,
        whole_bar=ci_bar(a.whole_file.low, a.whole_file.high, a.whole_file.estimate, a.margin)
        if a.whole_file
        else {"ok": False},
        full_rate=a.rates.get(FULL),
        none_rate=a.rates.get(NONE),
        file_monthly=file_monthly_usd(a),
        file_per_run=file_tokens_per_run(a),
        total_runs=len(res["runs"]),
        planned_runs=len(res["configs"]) * len(res["tasks"]) * res["repeats"],
        recorded=recorded_note,
        version=__version__,
    )


def write_report(a: Analysis, out: Path, *, recorded_note: dict | None = None) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(a, recorded_note=recorded_note), encoding="utf-8")
    return out
