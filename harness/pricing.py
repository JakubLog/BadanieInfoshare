"""Koszt kroku na podstawie `usage` z API i cennika z config/pricing.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

PRICING_FILE = Path(__file__).resolve().parent.parent / "config" / "pricing.yaml"


@lru_cache(maxsize=1)
def load_pricing() -> dict:
    return yaml.safe_load(PRICING_FILE.read_text())


def step_cost(model: str, usage: dict) -> float | None:
    """Koszt jednego wywołania API w USD albo None, gdy cennik nie zna modelu."""
    cfg = load_pricing()
    if not cfg.get("confirmed") or model not in cfg["models"]:
        return None
    inp = usage.get("input_tokens", 0) or 0
    cw = usage.get("cache_creation_input_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    prompt = inp + cw + cr
    tier = next(t for t in cfg["models"][model]["tiers"]
                if t["max_prompt_tokens"] is None or prompt <= t["max_prompt_tokens"])
    return (inp * tier["input"] + cw * tier["cache_write_5m"] + cr * tier["cache_read"] + out * tier["output"]) / 1e6
