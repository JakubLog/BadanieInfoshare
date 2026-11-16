"""Koszt wdrożenia wariantu = liczba niepustych linii kodu, które implementują wariant ulepszony.

- Python: linie między znacznikami `# [variant:<flaga>=<wartość>]` i `# [/variant]` (bez samych znaczników
  i komentarzy);
- szablony UI: niepuste linie w gałęziach `{% if V == "A" %}` (do `else`/`elif`/`endif` tego samego `if`), bez linii
  zawierających wyłącznie znaczniki gałęzi i bez komentarzy Jinja, oraz linie spoza gałęzi A z wyrażeniem `V == "A"`
  w treści (np. `"Następna strona" if V == "A" else "›"`). Wariant B ma własne gałęzie, które nie są liczone.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from harness.runlog import ANALYSIS_DIR
from klubfit.db import ROOT

MARK = re.compile(r"#\s*\[variant:([a-z_]+=[A-Za-z0-9]+)\]")
END = re.compile(r"#\s*\[/variant\]")
TPL_TAG = re.compile(r"{%-?\s*(if|elif|else|endif)\b(.*?)-?%}")
TPL_COMMENT = re.compile(r"{#.*?#}", re.S)


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


def template_loc(templates: Path | None = None) -> int:
    total = 0
    for p in sorted((templates or ROOT / "klubfit" / "ui" / "templates").glob("*.html")):
        # komentarze zastępujemy znakami nowej linii, żeby numeracja linii się nie przesunęła
        text = TPL_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), p.read_text(encoding="utf-8"))
        stack: list[bool] = []  # dla każdego otwartego if-a: czy jesteśmy w jego gałęzi A
        for line in text.splitlines():
            if not line.strip():
                continue
            counted = False
            pos = 0
            for m in [*TPL_TAG.finditer(line), None]:
                segment = line[pos:m.start() if m else len(line)].strip()
                if segment and (any(stack) or 'V == "A"' in segment):
                    counted = True  # tekst w gałęzi A albo wyrażenie warunkowe zależne od wariantu
                if m is None:
                    break
                kind = m.group(1)
                if any(stack) and not (kind != "if" and stack[-1]):
                    counted = True  # znacznik zagnieżdżonego if-a wewnątrz gałęzi A
                if kind == "if":
                    stack.append('V == "A"' in m.group(2))
                elif kind == "endif":
                    stack.pop()
                else:  # else / elif kończą gałąź A tego if-a
                    stack[-1] = False
                pos = m.end()
            total += counted
        assert not stack, f"niezamknięty if w {p.name}"
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
    (ANALYSIS_DIR / "variant_loc.json").write_text(json.dumps(loc, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(loc, indent=2, ensure_ascii=False))
