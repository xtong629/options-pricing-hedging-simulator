"""Plot six figures from an installed CLI 'all' run."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def render(run: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)

    def read(name):
        return json.loads((run / f"{name}.json").read_text())

    mc = read("mc")["convergence"]
    hedge = read("hedge")["summary"]
    risk = read("risk")
    n = risk["paths"]

    def save(name, title, x, y, context):
        plt.title(title, loc="left", weight="bold")
        plt.xlabel(x)
        plt.ylabel(y)
        plt.grid(axis="y", alpha=0.22)
        plt.figtext(0.02, 0.015, context, fontsize=8)
        plt.tight_layout(rect=(0, 0.05, 1, 1))
        plt.savefig(output / f"{name}.png", dpi=160)
        plt.close()

    for method in ("standard", "antithetic"):
        rows = [x for x in mc if x["kind"] == "call" and x["method"] == method]
        plt.loglog(
            [x["n_paths"] for x in rows], [x["rmse"] for x in rows], "o-", label=method
        )
    plt.legend()
    save(
        "convergence",
        "Call price convergence",
        "Paths (log scale)",
        "RMSE (CU/share, log scale)",
        f"Simulated 1y ATM call · IV 20% · {rows[0]['repeats']} runs per budget",
    )
    rows = [x for x in mc if x["n_paths"] == 100000]
    plt.bar(
        [f"{x['kind']}\n{x['method']}" for x in rows],
        [x["mean_squared_standard_error"] for x in rows],
    )
    save(
        "variance",
        "Estimator variance at equal path budgets",
        "",
        "Mean squared SE (CU²/share²)",
        f"Simulated 1y ATM · IV 20% · 100,000 paths · {rows[0]['repeats']} runs",
    )
    context = (
        f"Simulated short call · multiplier 100 · path vol = IV = 20% · {n:,} paths"
    )
    with np.load(run / "phase3_hedging_arrays.npz") as data:
        series = [data[f"v0.2_f{f}_c5_pnl"] for f in (1, 5)]
        bins = np.histogram_bin_edges(np.concatenate(series), bins=55)
        for sample, label in zip(series, ("Daily", "Weekly"), strict=True):
            plt.hist(sample, bins=bins, histtype="step", label=label, linewidth=1.7)
    plt.legend()
    save(
        "distribution",
        "Terminal P&L at 5 bps",
        "Net P&L (CU/contract)",
        "Path count",
        context,
    )
    for freq, label in [(1, "Daily"), (5, "Weekly")]:
        rows = [hedge[f"v0.2_f{freq}_c{c}"] for c in (0, 1, 5, 10)]
        plt.plot(
            [x["mean_costs"] for x in rows],
            [x["rmse"] for x in rows],
            "o-",
            label=label,
        )
    plt.legend()
    save(
        "cost",
        "Cost and net hedging error",
        "Mean nominal fees (CU/contract)",
        "Net RMSE (CU/contract)",
        context + " · 0/1/5/10 bps",
    )
    row = next(x for x in risk["scenarios"] if x["vol"] == 0.2 and x["bps"] == 5)
    for offset, key in [(-0.2, "daily"), (0.2, "weekly")]:
        plt.bar(
            np.arange(2) + offset, [row[key][m] for m in ("var", "es")], 0.4, label=key
        )
    plt.xticks([0, 1], ["95% VaR", "95% ES"])
    plt.legend()
    save("tail", "Tail losses at 5 bps", "", "Loss (CU/contract)", context)
    audit = risk["audit"]["explain"]
    terms = {k: sum(x["terms"][k] for x in audit) for k in audit[0]["terms"]}
    terms["residual"] = sum(x["residual"] for x in audit)
    plt.barh(list(terms), list(terms.values()))
    save(
        "attribution",
        "Path 0 · weekly hedge at 5 bps",
        "Contribution (CU/contract)",
        "",
        context + " · one audit path",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    render(args.run, args.output)
