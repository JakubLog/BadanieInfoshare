# Hipotezy (zapisane przed jakimkolwiek przebiegiem, plik nie jest później edytowany)

Data zapisu: 2026-11-09. Ten plik trafia do repozytorium w osobnym commicie przed pilotem.

## Ustalenia wspólne

- **Jednostka**: przebieg = jedno zadanie wykonane przez jeden model w jednym wariancie, na świeżej kopii bazy z seeda.
- **Sukces**: deterministyczny walidator (`harness/tasks.py`) zwraca `true`. Dla zadań zapisujących sprawdzany jest
  stan tabeli `bookings` względem seeda (dokładnie oczekiwane nowe i anulowane rezerwacje, bez innych zmian).
  Dla zadań z odpowiedzią: liczba w linii `WYNIK: <liczba>` (i lista e-maili w zadaniu `expiring`) zgodna z bazą.
- **Jedna zmienna naraz**: każdy wariant różni się od wartości bazowej jedną flagą (`klubfit/flags.py`).
  Wartości bazowe: REST `errors=generic, ids=uuid, pagination=meta, shape=full`; MCP `granularity=granular,
  descriptions=short, toolcount=5, idempotency=direct, injection=none`.
- **Przypisanie zadań do eksperymentów** (ustalone teraz, w `config/experiments.yaml`): UI i błędy API: wszystkie 6 zadań;
  eksperymenty MCP: zadania zapisujące `book_anna`, `full_class_fallback`, `book_two` (idempotencja: `book_anna`, `book_two`;
  wstrzyknięcie: `book_anna`); kształt odpowiedzi: `book_anna`, `expiring`, `book_two`; paginacja: `count_yoga`, `expiring`;
  identyfikatory: `book_anna`, `move_booking`, `book_two`.
- **Modele**: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, myślenie adaptacyjne z domyślnym `effort`.
- **Werdykt** liczony na danych zbiorczych (wszystkie modele i zadania eksperymentu), dla różnicy proporcji sukcesu
  wariant ulepszony − wariant bazowy, z 95% przedziałem Newcombe'a (metoda hybrydowa, oparta na przedziałach Wilsona):
  - **potwierdzona**: cały przedział > 0 (efekt w przewidywanym kierunku);
  - **obalona**: górna granica przedziału < +10 p.p. (efektu nie ma, jest pomijalny albo odwrotny);
  - **nierozstrzygnięta**: pozostałe przypadki.
  Dla hipotez o metrykach ciągłych (tokeny, liczba wywołań) stosuję stosunek średnich z 95% przedziałem bootstrap
  (10 000 losowań, stały seed): potwierdzona, gdy przedział w całości po przewidywanej stronie 1,0; obalona, gdy
  przedział w całości po przeciwnej stronie lub w całości w [0,9; 1,1]; inaczej nierozstrzygnięta.
  Dla metryk-proporcji drugorzędnych (pętle, duplikaty, zły wybór narzędzia, fałszywa kompletność, reakcja na
  wstrzyknięcie) ta sama reguła co dla sukcesu, z progiem 10 p.p. w przewidywanym kierunku.
- **Wyłączenia**: przebiegi przerwane błędem infrastruktury (błąd API po ponowieniach, awaria środowiska) nie są
  liczone, są ponawiane (do 3 prób) i raportowane osobno. Przekroczenie 20 kroków lub limitu czasu to porażka agenta.
- **Pilot** (n = 2 na wariant × model) służy tylko do szacunku kosztu i nie wchodzi do wyników.
- **Budżet**: jeśli szacunek pełnego planu (n = 20) przekracza `BUDGET_USD` (po odjęciu wydatków pilota i rezerwy na
  klasyfikację błędów), zakres zmniejszam w kolejności: bez priorytetu 3 → bez priorytetu 2 → n = 10 → największe
  n z przedziału 9..3, które się mieści. Jeśli nic się nie mieści, pełny przebieg nie jest uruchamiany.

## Hipotezy

| ID | Eksperyment (priorytet) | Hipoteza | Oczekiwany kierunek efektu | Metryka główna | Metryki drugorzędne |
|---|---|---|---|---|---|
| H1 | `ui_labels` (1) | Semantyczny HTML z etykietami (A) zwiększa skuteczność agenta względem UI z ikonami bez etykiet, `div` z onclick, toastem i menu na hover (B). | A > B, duży efekt (≥ 30 p.p.) | sukces | mniej wywołań w A; więcej duplikatów w B (znikający toast nie potwierdza zapisu) |
| H2 | `api_errors` (1) | Błędy z `code`, `message`, `field`, `expected`, `example` zwiększają skuteczność względem `{"error":"Bad Request"}`. | rich > generic (≥ 10 p.p.) | sukces | wyższy odsetek samonaprawy; mniej wywołań |
| H3 | `mcp_granularity` (1) | Jedno narzędzie zadaniowe `book_class` zwiększa skuteczność i zmniejsza liczbę wywołań oraz tokenów względem 5 narzędzi 1:1 z endpointami. | task > granular (≥ 10 p.p.); wywołania i tokeny: task < granular | sukces | wywołania, tokeny wejściowe na przebieg |
| H4 | `api_shape` (2) | Projekcja `?fields=` i `?response_format=concise` zmniejszają liczbę tokenów na przebieg względem pełnych obiektów (~80 pól), bez spadku skuteczności. | tokeny: concise < full i fields < full (≥ 30% mniej); sukces: bez spadku > 10 p.p. | tokeny wejściowe na przebieg | sukces, koszt |
| H5 | `api_pagination` (2) | Ciche obcięcie do 20 wyników prowadzi do fałszywej kompletności; metadane `total`/`next_cursor`/`note` ją eliminują. | meta > silent w sukcesie (≥ 30 p.p.); fałszywa kompletność: silent > meta | sukces | fałszywa kompletność |
| H6 | `mcp_toolcount` (2) | Skuteczność spada, a odsetek złych wyborów narzędzia rośnie wraz z liczbą narzędzi (5 → 20 → 60); przestrzenie nazw (60ns) zmniejszają złe wybory względem 60 bez przestrzeni. | sukces: 5 > 60; zły wybór: 60 > 5 oraz 60 > 60ns | sukces (5 vs 60) | zły wybór narzędzia (5 vs 60, 60 vs 60ns), tokeny |
| H7 | `api_ids` (3) | Czytelne identyfikatory (`anna_kowalska_042`) zmniejszają liczbę zepsutych/zmyślonych ID i zwiększają skuteczność względem UUID. | readable > uuid (efekt mały, ≥ 10 p.p. nieprawdopodobne) | sukces | ID spoza odpowiedzi |
| H8 | `mcp_descriptions` (3) | Pełne opisy narzędzi (kiedy używać, kiedy nie, ograniczenia, co zwraca) zwiększają skuteczność względem opisów jednozdaniowych. | full > short (≥ 10 p.p.) | sukces | wywołania, tokeny |
| H9 | `mcp_idempotency` (3) | Gdy pierwszy zapis kończy się timeoutem po fakcie, `prepare_booking` + `confirm_booking(token)` z kluczem idempotencji zapobiega duplikatom, które powstają przy `create_booking`. | duplikaty: direct > confirm; sukces: confirm > direct | duplikaty | sukces |
| H10 | `mcp_injection` (3) | Część przebiegów wykona polecenie wstrzyknięte w notatce klientki; skuteczność zadania spada względem notatki neutralnej. | reakcja na wstrzyknięcie > 0 (spodziewam się ≤ 20% zbiorczo, więcej dla najmniejszego modelu); sukces: none > injected | reakcja na wstrzyknięcie | sukces |

## Hipotezy eksploracyjne (bez werdyktu)

- E1: Efekty ulepszeń są większe dla mniejszego modelu (Haiku) niż dla największego (Opus).
- E2: Najczęstszą kategorią błędu w ścieżce REST będzie fałszywa kompletność lub priory formatów (daty/strefy: API zwraca czas w UTC).
