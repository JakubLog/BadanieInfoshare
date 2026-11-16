.PHONY: all setup test seed smoke pilot full tables analyze

# Pełny cykl: środowisko -> testy -> seed -> pilot + szacunek -> pełny przebieg (jeśli mieści się w BUDGET_USD) -> analiza.
# Nowy pomiar obok opublikowanych logów: RUNS_DIR=runs_repro ANALYSIS_DIR=analysis_repro make all
all: setup test seed pilot full analyze

setup:
	uv sync
	uv run playwright install chromium

test:
	uv run pytest -q

seed:
	uv run python -m klubfit.seed

# jeden tani przebieg z prawdziwym API (Haiku, REST) do sprawdzenia klucza i harnessu przed pilotem
smoke:
	uv run python -m harness.runner one --experiment api_errors --variant rich --model claude-haiku-5-5 --task book_anna

# n=2 na wariant × model; zapisuje ESTIMATE.md i plan.json w katalogu przebiegów
pilot:
	uv run python -m harness.runner pilot

# zakres i n z plan.json; przebiegi już zakończone są pomijane (wznawialne)
full:
	uv run python -m harness.runner full

# tabele, liczby z logów i wykresy z istniejących logów (bez wywołań modelu)
tables:
	uv run python -m analysis.variant_loc
	uv run python -m analysis.analyze
	uv run python -m analysis.log_checks
	uv run python -m analysis.charts

# tabele + taksonomia błędów (woła model tylko dla nieotagowanych porażek)
analyze: tables
	uv run python -m analysis.taxonomy
