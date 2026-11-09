# Wyniki (wygenerowane przez analysis/analyze.py)

Przebiegi liczone: 4380; przerwane błędem infrastruktury (nieliczone): 0.
Okres przebiegów: 2026-11-09T22:01:59.767940+00:00 – 2026-11-09T23:03:31.521873+00:00 (UTC).
Koszt: pełny przebieg 105.45 USD, pilot 3.79 USD, wszystkie logi łącznie (z klasyfikatorem) 111.62 USD.
Powody zakończenia przebiegów: {'end_turn': 4270, 'max_steps': 110}.

## ui_labels (priorytet 1, ścieżka ui; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B | 360 | 60% | [55–65%] | 19.6 | 72169 | 1764 | 0.0447 | 737/1284 (57%) | 14/360 (4%) | 0/120 (0%) | 118/360 (33%) | — | 0/360 (0%) | — |
| A | 360 | 100% | [99–100%] | 13.8 | 76752 | 1430 | 0.0474 | 19/19 (100%) | 2/360 (1%) | 0/120 (0%) | 0/360 (0%) | — | 0/360 (0%) | — |

Sukces per model:

| model | B | A |
|---|---|---|
| claude-haiku-5-5 | 35% [27–44%] | 100% [97–100%] |
| claude-opus-5-5 | 100% [97–100%] | 100% [97–100%] |
| claude-sonnet-5-5 | 45% [36–54%] | 100% [97–100%] |

Sukces per zadanie:

| zadanie | B | A |
|---|---|---|
| book_anna | 42% (n=60) | 100% (n=60) |
| count_yoga | 90% (n=60) | 100% (n=60) |
| move_booking | 52% (n=60) | 100% (n=60) |
| expiring | 100% (n=60) | 100% (n=60) |
| full_class_fallback | 37% (n=60) | 100% (n=60) |
| book_two | 40% (n=60) | 100% (n=60) |

## api_errors (priorytet 1, ścieżka rest; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| generic | 360 | 99% | [98–100%] | 5.1 | 35617 | 1367 | 0.0272 | — | 0/360 (0%) | 0/120 (0%) | 0/360 (0%) | — | 0/360 (0%) | — |
| rich | 360 | 99% | [97–100%] | 5.1 | 35511 | 1363 | 0.0270 | — | 0/360 (0%) | 0/120 (0%) | 0/360 (0%) | — | 0/360 (0%) | — |

Sukces per model:

| model | generic | rich |
|---|---|---|
| claude-haiku-5-5 | 98% [94–100%] | 97% [92–99%] |
| claude-opus-5-5 | 100% [97–100%] | 100% [97–100%] |
| claude-sonnet-5-5 | 100% [97–100%] | 100% [97–100%] |

Sukces per zadanie:

| zadanie | generic | rich |
|---|---|---|
| book_anna | 100% (n=60) | 100% (n=60) |
| count_yoga | 100% (n=60) | 100% (n=60) |
| move_booking | 100% (n=60) | 100% (n=60) |
| expiring | 100% (n=60) | 100% (n=60) |
| full_class_fallback | 97% (n=60) | 93% (n=60) |
| book_two | 100% (n=60) | 100% (n=60) |

## mcp_granularity (priorytet 1, ścieżka mcp; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| granular | 180 | 99% | [97–100%] | 6.0 | 13769 | 918 | 0.0120 | — | 0/180 (0%) | — | 0/180 (0%) | 0/180 (0%) | 0/180 (0%) | — |
| task | 180 | 100% | [98–100%] | 1.7 | 4212 | 506 | 0.0064 | 60/60 (100%) | 0/180 (0%) | — | 0/180 (0%) | 0/180 (0%) | 0/180 (0%) | — |

Sukces per model:

| model | granular | task |
|---|---|---|
| claude-haiku-5-5 | 98% [91–100%] | 100% [94–100%] |
| claude-opus-5-5 | 100% [94–100%] | 100% [94–100%] |
| claude-sonnet-5-5 | 100% [94–100%] | 100% [94–100%] |

Sukces per zadanie:

| zadanie | granular | task |
|---|---|---|
| book_anna | 100% (n=60) | 100% (n=60) |
| full_class_fallback | 98% (n=60) | 100% (n=60) |
| book_two | 100% (n=60) | 100% (n=60) |

## api_shape (priorytet 2, ścieżka rest; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| full | 180 | 100% | [98–100%] | 4.5 | 26975 | 1375 | 0.0247 | — | 0/180 (0%) | 0/60 (0%) | 0/180 (0%) | — | 0/180 (0%) | — |
| fields | 180 | 100% | [98–100%] | 4.4 | 26682 | 1375 | 0.0289 | 6/9 (67%) | 0/180 (0%) | 0/60 (0%) | 0/180 (0%) | — | 0/180 (0%) | — |
| concise | 180 | 100% | [98–100%] | 4.2 | 20748 | 1281 | 0.0256 | — | 0/180 (0%) | 0/60 (0%) | 0/180 (0%) | — | 0/180 (0%) | — |

Sukces per model:

| model | full | fields | concise |
|---|---|---|---|
| claude-haiku-5-5 | 100% [94–100%] | 100% [94–100%] | 100% [94–100%] |
| claude-opus-5-5 | 100% [94–100%] | 100% [94–100%] | 100% [94–100%] |
| claude-sonnet-5-5 | 100% [94–100%] | 100% [94–100%] | 100% [94–100%] |

Sukces per zadanie:

| zadanie | full | fields | concise |
|---|---|---|---|
| book_anna | 100% (n=60) | 100% (n=60) | 100% (n=60) |
| expiring | 100% (n=60) | 100% (n=60) | 100% (n=60) |
| book_two | 100% (n=60) | 100% (n=60) | 100% (n=60) |

## api_pagination (priorytet 2, ścieżka rest; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| silent | 120 | 99% | [95–100%] | 2.9 | 20737 | 1287 | 0.0245 | — | 0/120 (0%) | 1/120 (1%) | 0/120 (0%) | — | 0/120 (0%) | — |
| meta | 120 | 100% | [97–100%] | 2.6 | 20006 | 1152 | 0.0186 | — | 0/120 (0%) | 0/120 (0%) | 0/120 (0%) | — | 0/120 (0%) | — |

Sukces per model:

| model | silent | meta |
|---|---|---|
| claude-haiku-5-5 | 98% [87–100%] | 100% [91–100%] |
| claude-opus-5-5 | 100% [91–100%] | 100% [91–100%] |
| claude-sonnet-5-5 | 100% [91–100%] | 100% [91–100%] |

Sukces per zadanie:

| zadanie | silent | meta |
|---|---|---|
| count_yoga | 98% (n=60) | 100% (n=60) |
| expiring | 100% (n=60) | 100% (n=60) |

## mcp_toolcount (priorytet 2, ścieżka mcp; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 180 | 98% | [95–99%] | 5.8 | 13441 | 901 | 0.0118 | — | 0/180 (0%) | — | 0/180 (0%) | 0/180 (0%) | 0/180 (0%) | — |
| 20 | 180 | 99% | [96–100%] | 5.9 | 21643 | 888 | 0.0128 | — | 0/180 (0%) | — | 0/180 (0%) | 0/180 (0%) | 0/180 (0%) | — |
| 60 | 180 | 98% | [94–99%] | 5.8 | 41219 | 885 | 0.0143 | — | 0/180 (0%) | — | 0/180 (0%) | 0/180 (0%) | 0/180 (0%) | — |
| 60ns | 180 | 99% | [96–100%] | 5.8 | 42391 | 903 | 0.0150 | — | 0/180 (0%) | — | 0/180 (0%) | 0/180 (0%) | 0/180 (0%) | — |

Sukces per model:

| model | 5 | 20 | 60 | 60ns |
|---|---|---|---|---|
| claude-haiku-5-5 | 95% [86–98%] | 97% [89–99%] | 93% [84–97%] | 97% [89–99%] |
| claude-opus-5-5 | 100% [94–100%] | 100% [94–100%] | 100% [94–100%] | 100% [94–100%] |
| claude-sonnet-5-5 | 100% [94–100%] | 100% [94–100%] | 100% [94–100%] | 100% [94–100%] |

Sukces per zadanie:

| zadanie | 5 | 20 | 60 | 60ns |
|---|---|---|---|---|
| book_anna | 100% (n=60) | 100% (n=60) | 100% (n=60) | 100% (n=60) |
| full_class_fallback | 95% (n=60) | 97% (n=60) | 93% (n=60) | 97% (n=60) |
| book_two | 100% (n=60) | 100% (n=60) | 100% (n=60) | 100% (n=60) |

## api_ids (priorytet 3, ścieżka rest; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| uuid | 180 | 100% | [98–100%] | 6.3 | 45255 | 1398 | 0.0258 | — | 0/180 (0%) | — | 0/180 (0%) | — | 0/180 (0%) | — |
| readable | 180 | 100% | [98–100%] | 6.2 | 43174 | 1233 | 0.0299 | — | 0/180 (0%) | — | 0/180 (0%) | — | 0/180 (0%) | — |

Sukces per model:

| model | uuid | readable |
|---|---|---|
| claude-haiku-5-5 | 100% [94–100%] | 100% [94–100%] |
| claude-opus-5-5 | 100% [94–100%] | 100% [94–100%] |
| claude-sonnet-5-5 | 100% [94–100%] | 100% [94–100%] |

Sukces per zadanie:

| zadanie | uuid | readable |
|---|---|---|
| book_anna | 100% (n=60) | 100% (n=60) |
| move_booking | 100% (n=60) | 100% (n=60) |
| book_two | 100% (n=60) | 100% (n=60) |

## mcp_descriptions (priorytet 3, ścieżka mcp; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| short | 180 | 99% | [97–100%] | 5.9 | 13701 | 903 | 0.0116 | — | 0/180 (0%) | — | 0/180 (0%) | 0/180 (0%) | 0/180 (0%) | — |
| full | 180 | 99% | [97–100%] | 7.5 | 20252 | 1097 | 0.0143 | — | 0/180 (0%) | — | 0/180 (0%) | 0/180 (0%) | 0/180 (0%) | — |

Sukces per model:

| model | short | full |
|---|---|---|
| claude-haiku-5-5 | 98% [91–100%] | 98% [91–100%] |
| claude-opus-5-5 | 100% [94–100%] | 100% [94–100%] |
| claude-sonnet-5-5 | 100% [94–100%] | 100% [94–100%] |

Sukces per zadanie:

| zadanie | short | full |
|---|---|---|
| book_anna | 100% (n=60) | 100% (n=60) |
| full_class_fallback | 98% (n=60) | 98% (n=60) |
| book_two | 100% (n=60) | 100% (n=60) |

## mcp_idempotency (priorytet 3, ścieżka mcp; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| direct | 120 | 100% | [97–100%] | 6.6 | 16929 | 1231 | 0.0176 | 60/60 (100%) | 0/120 (0%) | — | 0/120 (0%) | 0/120 (0%) | 0/120 (0%) | — |
| confirm | 120 | 100% | [97–100%] | 7.3 | 19046 | 1176 | 0.0175 | 120/120 (100%) | 0/120 (0%) | — | 0/120 (0%) | 0/120 (0%) | 0/120 (0%) | — |

Sukces per model:

| model | direct | confirm |
|---|---|---|
| claude-haiku-5-5 | 100% [91–100%] | 100% [91–100%] |
| claude-opus-5-5 | 100% [91–100%] | 100% [91–100%] |
| claude-sonnet-5-5 | 100% [91–100%] | 100% [91–100%] |

Sukces per zadanie:

| zadanie | direct | confirm |
|---|---|---|
| book_anna | 100% (n=60) | 100% (n=60) |
| book_two | 100% (n=60) | 100% (n=60) |

## mcp_injection (priorytet 3, ścieżka mcp; przerwane infra: 0)

| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 60 | 100% | [94–100%] | 3.9 | 10908 | 696 | 0.0103 | — | 0/60 (0%) | — | 0/60 (0%) | 0/60 (0%) | 0/60 (0%) | 0/60 (0%) |
| injected | 60 | 100% | [94–100%] | 3.6 | 10754 | 922 | 0.0139 | — | 0/60 (0%) | — | 0/60 (0%) | 0/60 (0%) | 0/60 (0%) | 0/60 (0%) |

Sukces per model:

| model | none | injected |
|---|---|---|
| claude-haiku-5-5 | 100% [84–100%] | 100% [84–100%] |
| claude-opus-5-5 | 100% [84–100%] | 100% [84–100%] |
| claude-sonnet-5-5 | 100% [84–100%] | 100% [84–100%] |

Sukces per zadanie:

| zadanie | none | injected |
|---|---|---|
| book_anna | 100% (n=60) | 100% (n=60) |

## Hipotezy

| hipoteza | porównanie | metryka | wynik | 95% CI | werdykt |
|---|---|---|---|---|---|
| H1 | A − B | success (360/360 vs 216/360) | +40 p.p. | [+35; +45] | potwierdzona |
| H2 | rich − generic | success (356/360 vs 358/360) | -1 p.p. | [-2; +1] | obalona |
| H3 | task − granular | success (180/180 vs 179/180) | +1 p.p. | [-2; +3] | obalona |
| H4 (concise) | concise / full | tokens_in (stosunek średnich) | 0.77 | [0.70–0.85] | potwierdzona |
| H4 (fields) | fields / full | tokens_in (stosunek średnich) | 0.99 | [0.91–1.08] | obalona |
| H5 | meta − silent | success (120/120 vs 119/120) | +1 p.p. | [-2; +5] | obalona |
| H6 (sukces 5 vs 60) | 5 − 60 | success (177/180 vs 176/180) | +1 p.p. | [-3; +4] | obalona |
| H6 (zły wybór 60 vs 5) | 60 − 5 | wrong_tool (0/180 vs 0/180) | +0 p.p. | [-2; +2] | obalona |
| H6 (zły wybór 60ns vs 60) | 60ns − 60 | wrong_tool (0/180 vs 0/180) | +0 p.p. | [-2; +2] | obalona |
| H7 | readable − uuid | success (180/180 vs 180/180) | +0 p.p. | [-2; +2] | obalona |
| H8 | full − short | success (179/180 vs 179/180) | +0 p.p. | [-3; +3] | obalona |
| H9 | confirm − direct | duplicates (0/120 vs 0/120) | +0 p.p. | [-3; +3] | obalona |
| H10 | injected − none | injection_reaction (0/60 vs 0/60) | +0 p.p. | [-6; +6] | obalona |

## Efekt do kosztu wdrożenia

| zmiana | Δ sukcesu | 95% CI | linie kodu | p.p. na linię |
|---|---|---|---|---|
| ui_labels: B → A | +40 p.p. | [+35; +45] | 48 | 0.83 |
| mcp_toolcount: 60 → 60ns | +1 p.p. | [-2; +5] | 3 | 0.37 |
| api_pagination: silent → meta | +1 p.p. | [-2; +5] | 18 | 0.05 |
| mcp_granularity: granular → task | +1 p.p. | [-2; +3] | 50 | 0.01 |
| api_errors: generic → rich | -1 p.p. | [-2; +1] | 19 | -0.03 |
| api_shape: full → concise | +0 p.p. | [-2; +2] | 27 | 0.00 |
| api_shape: full → fields | +0 p.p. | [-2; +2] | 12 | 0.00 |
| api_ids: uuid → readable | +0 p.p. | [-2; +2] | 59 | 0.00 |
| mcp_descriptions: short → full | +0 p.p. | [-3; +3] | 32 | 0.00 |
| mcp_idempotency: direct → confirm | +0 p.p. | [-3; +3] | 39 | 0.00 |
