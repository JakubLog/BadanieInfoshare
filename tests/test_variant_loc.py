"""Liczenie linii wariantu A w szablonach: gałęzie w jednej linii, else, komentarze i wyrażenia warunkowe."""

from analysis.variant_loc import template_loc

TEMPLATE = """{# komentarz z V == "A" nie jest kodem #}
{% if V == "A" %}
<nav>menu</nav>
{% if msg %}<div role="status">{{ msg }}</div>{% endif %}
{% else %}
<div class="burger">☰</div>
{% endif %}
{%- if V == "A" -%}<button>Zapisz</button>{%- else -%}<div>＋</div>{%- endif -%}
<p>{{ "Dalej" if V == "A" else "›" }}</p>
<p>wspólne</p>
"""


def test_counts_only_variant_a_lines(tmp_path):
    (tmp_path / "t.html").write_text(TEMPLATE, encoding="utf-8")
    # <nav>, zagnieżdżony if z komunikatem, jednolinijkowy if z przyciskiem, wyrażenie warunkowe
    assert template_loc(tmp_path) == 4


def test_repository_templates():
    assert template_loc() == 24
