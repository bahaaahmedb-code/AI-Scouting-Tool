"""Fact registry: every number written into a chatbot answer goes through these formatters.

The registry records each displayed numeral. `check_numbers(text, facts)` extracts all numerals from a
final answer (template or LLM-rephrased) and reports which ones are not backed by a computed value.
"""
from __future__ import annotations

import math
import re

NUM_RE = re.compile(r"(?<![A-Za-z_])\d[\d,]*(?:\.\d+)?")
LIST_MARKER_RE = re.compile(r"(?m)^\s*(?:\d+\.|#\d+)\s")


def _norm(s: str) -> str:
    s = s.replace(",", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".") or "0"
    return s


class Facts:
    def __init__(self, always: set[str] | None = None):
        self.items: set[str] = set(always or ())
        self.log: list[tuple[str, float | str]] = []

    def _add(self, shown: str, raw) -> str:
        for n in NUM_RE.findall(shown):
            self.items.add(_norm(n))
        self.log.append((shown, raw))
        return shown

    # ---- formatters ----
    def eur(self, x: float) -> str:
        m = x / 1e6
        return self._add(f"£{m:,.1f}m" if m >= 0.95 or m == 0 else f"£{x / 1e3:,.0f}k", x)

    def pct(self, x: float, signed: bool = True, nd: int = 0) -> str:
        return self._add(f"{x:+.{nd}f}%" if signed else f"{x:.{nd}f}%", x)

    def pm(self, x: float) -> str:
        return self._add(f"±{x:.0f}%", x)

    def num(self, x: float, nd: int = 2) -> str:
        return self._add(f"{x:,.{nd}f}", x)

    def int(self, x) -> str:
        return self._add(f"{int(round(float(x))):,}", x)

    def times(self, x: float) -> str:
        return self._add(f"{x:.1f}×", x)

    def raw(self, s) -> str:
        """Register a value that is already a computed string (e.g. a season label)."""
        return self._add(str(s), s)

    def allow(self, *vals):
        for v in vals:
            for n in NUM_RE.findall(str(v)):
                self.items.add(_norm(n))

    def fmt_feature(self, f: str, v) -> str:
        """notebook fmt_val"""
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "n/a"
        if isinstance(v, str):
            return v
        if f == "minutes":
            return self.int(v)
        if f == "age":
            return self.int(v)
        if f == "pass_accuracy":
            return self._add(f"{v:.1f}%", v)
        if f == "start_share":
            return self._add(f"{v * 100:.0f}% of matches", v)
        return self.num(v, 2)


def check_numbers(text: str, facts: Facts) -> dict:
    body = LIST_MARKER_RE.sub(" ", text or "")
    found = [_norm(n) for n in NUM_RE.findall(body)]
    unmatched = [n for n in found if n not in facts.items]
    return {"total": len(found), "matched": len(found) - len(unmatched), "unmatched": unmatched}
