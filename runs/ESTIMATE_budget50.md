# Szacunek kosztu pełnego przebiegu (wygenerowane przez harness/estimate.py)

- BUDGET_USD: 50.00
- Wydano do tej pory (pilot i przebiegi testowe, suma kroków z logów): 3.7853 USD
- Rezerwa na klasyfikację błędów (TAGGER_RESERVE_USD): 3.00 USD
- Dostępne na pełny przebieg: 43.2147 USD
- Modele: claude-opus-5-5, claude-sonnet-5-5, claude-haiku-5-5

## Średni koszt przebiegu w pilocie (USD)

| eksperyment | priorytet | claude-opus-5-5 | claude-sonnet-5-5 | claude-haiku-5-5 | przebiegi pilota (OK/infra) |
|---|---|---|---|---|---|
| ui_labels | 1 | 0.0744 | 0.0390 | 0.0034 | 12/0 |
| api_errors | 1 | 0.0604 | 0.0356 | 0.0020 | 12/0 |
| mcp_granularity | 1 | 0.0259 | 0.0125 | 0.0009 | 12/0 |
| api_shape | 2 | 0.0764 | 0.0451 | 0.0022 | 18/0 |
| api_pagination | 2 | 0.0586 | 0.0245 | 0.0019 | 12/0 |
| mcp_toolcount | 2 | 0.0486 | 0.0210 | 0.0015 | 24/0 |
| api_ids | 3 | 0.0938 | 0.0392 | 0.0018 | 12/0 |
| mcp_descriptions | 3 | 0.0349 | 0.0161 | 0.0013 | 12/0 |
| mcp_idempotency | 3 | 0.0392 | 0.0190 | 0.0012 | 12/0 |
| mcp_injection | 3 | 0.0203 | 0.0121 | 0.0007 | 12/0 |

Średni koszt przebiegu (wszystkie modele i eksperymenty): 0.0274 USD (n=138).

## Warianty zakresu

| zakres | n | szacowany koszt (USD) | mieści się |
|---|---|---|---|
| pełny plan (priorytety 1–3), n=20 | 20 | 130.92 | nie |
| bez priorytetu 3, n=20 | 20 | 102.40 | nie |
| tylko priorytet 1, n=20 | 20 | 56.28 | nie |
| tylko priorytet 1, n=10 | 10 | 28.14 | tak |

**Decyzja:** tylko priorytet 1, n=10 (eksperymenty: ui_labels, api_errors, mcp_granularity), szacunek 28.14 USD. Twardy limit w runnerze: łączny koszt wszystkich logów ≤ 47.00 USD.
