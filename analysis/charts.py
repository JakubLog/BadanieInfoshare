"""Wykresy PNG do analysis/charts/ na podstawie analysis/results.json."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from analysis.common import ANALYSIS  # noqa: E402

CHARTS = ANALYSIS / "charts"
BEFORE_AFTER = [("UI: etykiety", "ui_labels", "B", "A"), ("REST: błędy", "api_errors", "generic", "rich"),
                ("MCP: ziarnistość", "mcp_granularity", "granular", "task"),
                ("REST: paginacja", "api_pagination", "silent", "meta"),
                ("REST: kształt (concise)", "api_shape", "full", "concise"),
                ("REST: identyfikatory", "api_ids", "uuid", "readable"),
                ("MCP: opisy", "mcp_descriptions", "short", "full"),
                ("MCP: idempotencja", "mcp_idempotency", "direct", "confirm")]


def _err(s):
    return [[100 * (s["p"] - s["lo"])], [100 * (s["hi"] - s["p"])]]


def success_before_after(res: dict) -> None:
    items = [(lbl, res["experiments"][e]["variants"][a], res["experiments"][e]["variants"][b])
             for lbl, e, a, b in BEFORE_AFTER
             if e in res["experiments"] and a in res["experiments"][e]["variants"] and b in res["experiments"][e]["variants"]]
    if not items:
        return
    fig, ax = plt.subplots(figsize=(max(6, 1.6 * len(items)), 4.5))
    w = 0.38
    for i, (lbl, before, after) in enumerate(items):
        ax.bar(i - w / 2, 100 * before["p"], w, yerr=_err(before), capsize=3, color="#b0b0b0", label="przed" if i == 0 else None)
        ax.bar(i + w / 2, 100 * after["p"], w, yerr=_err(after), capsize=3, color="#2a7ab9", label="po" if i == 0 else None)
    ax.set_xticks(range(len(items)), [lbl for lbl, _, _ in items], rotation=20, ha="right")
    ax.set_ylabel("sukces [%] (95% CI Wilsona)")
    ax.set_ylim(0, 105)
    ax.legend()
    ax.set_title("Sukces przed i po zmianie (wszystkie modele i zadania)")
    fig.tight_layout()
    fig.savefig(CHARTS / "success_before_after.png", dpi=150)
    plt.close(fig)


def tokens_per_variant(res: dict) -> None:
    exps = list(res["experiments"].items())
    fig, axes = plt.subplots(1, len(exps), figsize=(2.4 * len(exps), 4), sharey=False)
    axes = axes if len(exps) > 1 else [axes]
    for ax, (name, e) in zip(axes, exps):
        vs = list(e["variants"])
        ax.bar(vs, [e["variants"][v]["tokens_in"] / 1000 for v in vs], color="#2a7ab9")
        ax.set_title(name, fontsize=8)
        ax.tick_params(axis="x", labelsize=7, rotation=30)
    axes[0].set_ylabel("tokeny wejściowe na przebieg [tys.]")
    fig.suptitle("Tokeny wejściowe na przebieg (średnia) per wariant")
    fig.tight_layout()
    fig.savefig(CHARTS / "tokens_per_variant.png", dpi=150)
    plt.close(fig)


def toolcount_vs_wrong(res: dict) -> None:
    e = res["experiments"].get("mcp_toolcount")
    if not e:
        return
    order = [v for v in ["5", "20", "60", "60ns"] if v in e["variants"]]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(order, [100 * e["variants"][v]["wrong_tool"]["p"] for v in order], "o-", color="#c0392b",
            label="przebiegi ze złym wyborem narzędzia")
    ax.plot(order, [100 * e["variants"][v]["p"] for v in order], "s--", color="#2a7ab9", label="sukces")
    for m, d in e["by_model"].items():
        ax.plot(order, [100 * d[v]["wrong_tool"]["p"] if v in d else float("nan") for v in order], ":", alpha=0.6,
                label=f"zły wybór: {m}")
    ax.set_xlabel("liczba narzędzi (60ns = z przestrzeniami nazw)")
    ax.set_ylabel("%")
    ax.set_ylim(0, 105)
    ax.legend(fontsize=7)
    ax.set_title("Liczba narzędzi a zły wybór narzędzia")
    fig.tight_layout()
    fig.savefig(CHARTS / "toolcount_vs_wrong_tool.png", dpi=150)
    plt.close(fig)


def main() -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    res = json.loads((ANALYSIS / "results.json").read_text())
    success_before_after(res)
    tokens_per_variant(res)
    toolcount_vs_wrong(res)
    print(f"Wykresy: {sorted(p.name for p in CHARTS.glob('*.png'))}")


if __name__ == "__main__":
    main()
