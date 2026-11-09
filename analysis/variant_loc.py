"""Koszt wdrożenia wariantu = liczba niepustych linii kodu, które implementują wariant ulepszony.

- Python: linie między znacznikami `# [variant:<flaga>=<wartość>]` i `# [/variant]` (bez samych znaczników
  i komentarzy);
- szablony UI: linie w gałęziach `{% if V == "A" %}` (do `else`/`endif` na tym samym poziomie) oraz linie
  z wyrażeniem `V == "A"` w treści.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from klubfit.db import ROOT

MARK = re.compile(r"#\s*\[variant:([a-z_]+=[A-Za-z0-9]+)\]")
END = re.compile(r"#\s*\[/variant\]")
TPL_IF_A = re.compile(r'{%-?\s*if V == "A"\s*-?%}')
TPL_IF = re.compile(r"{%-?\s*if\b")
TPL_ELSE = re.compile(r"{%-?\s*(else|elif)\b")
TPL_END = re.compile(r"{%-?\s*endif\b")


def python_loc() -> dict[str, int]:
    """Linie liczone dla każdego otwartego znacznika (znaczniki mogą być zagnieżdżone)."""
    out: dict[str, int] = defaultdict(int)
    for p in sorted((ROOT / "klubfit").rglob("*.py")):
        open_marks: list[str] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            m = MARK.search(line)
            if m:
                open_marks.append(m.group(1))
                continue
            if END.search(line):
                open_marks.pop()
                continue
            s = line.strip()
            if s and not s.startswith("#"):
                for mark in set(open_marks):
                    out[mark] += 1
    return dict(out)


def template_loc() -> int:
    total = 0
    for p in sorted((ROOT / "klubfit" / "ui" / "templates").glob("*.html")):
        depth_stack: list[bool] = []  # True = jesteśmy w gałęzi A tego if-a
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            in_a = any(depth_stack)
            if TPL_IF_A.search(s):
                depth_stack.append(True)
                continue
            if TPL_IF.search(s):
                depth_stack.append(False)
                if in_a:
                    total += 1
                continue
            if TPL_ELSE.search(s) and depth_stack:
                if depth_stack[-1]:
                    depth_stack[-1] = False
                elif in_a:
                    total += 1
                continue
            if TPL_END.search(s) and depth_stack:
                depth_stack.pop()
                if any(depth_stack):
                    total += 1
                continue
            if s and (in_a or 'V == "A"' in s):
                total += 1
    return total


def error_detail_loc() -> int:
    """Linie z treścią błędów (expected=/example=) w domenie i API: koszt napisania „bogatych” komunikatów."""
    n = 0
    for p in [*(ROOT / "klubfit" / "domain").rglob("*.py"), *(ROOT / "klubfit" / "api").rglob("*.py"),
              ROOT / "klubfit" / "bridge.py"]:
        n += sum(1 for line in p.read_text(encoding="utf-8").splitlines() if "expected=" in line or "example=" in line)
    return n


def variant_loc() -> dict[str, int]:
    loc = python_loc()
    loc["ui=A"] = template_loc()
    loc["errors=rich+content"] = loc.get("errors=rich", 0) + error_detail_loc()
    return loc


if __name__ == "__main__":
    loc = variant_loc()
    (ROOT / "analysis" / "variant_loc.json").write_text(json.dumps(loc, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(loc, indent=2, ensure_ascii=False))
