.PHONY: all setup test seed smoke pilot full analyze

# Pełny cykl: środowisko -> testy -> seed -> pilot + szacunek -> pełny przebieg (jeśli mieści się w BUDGET_USD) -> analiza.
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

# n=2 na wariant × model; zapisuje runs/ESTIMATE.md i runs/plan.json
pilot:
	uv run python -m harness.runner pilot

# zakres i n z runs/plan.json; przebiegi już zakończone są pomijane (wznawialne)
full:
	uv run python -m harness.runner full

analyze:
	uv run python -m analysis.analyze
	uv run python -m analysis.taxonomy
	uv run python -m analysis.charts
	uv run python -m analysis.variant_loc
