"""Reproduce Phase 3 terminal arrays and summary with shared paths."""

import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import scipy

from optionlab import EuropeanOption, MarketSnapshot, OptionType
from optionlab.hedging import physical_paths, simulate_hedge


def main():
    """Save results under /tmp; each batch is shared across all strategies."""
    started = time.perf_counter()
    option = EuropeanOption(OptionType.CALL, 100, 1, 100)
    market = MarketSnapshot(100, 0.03, 0, 0.2)
    rng = np.random.default_rng(20261122)
    outputs = {}
    for volatility in (0.15, 0.2, 0.3):
        for start in range(0, 10_000, 512):
            size = min(512, 10_000 - start)
            z = rng.standard_normal((252, size))
            paths = physical_paths(100, 0.05, 0, volatility, 1 / 252, z)
            for frequency in (1, 5):
                for bps in (0, 1, 5, 10):
                    result = simulate_hedge(option, market, paths, frequency, bps)
                    key = f"v{volatility}_f{frequency}_c{bps}"
                    bucket = outputs.setdefault(
                        key,
                        {
                            name: []
                            for name in (
                                "pnl",
                                "turnover",
                                "costs",
                                "trades",
                                "cost_impact",
                            )
                        },
                    )
                    for name in bucket:
                        bucket[name].append(getattr(result, name))
    arrays = {
        f"{key}_{name}": np.concatenate(values)
        for key, bucket in outputs.items()
        for name, values in bucket.items()
    }
    np.savez_compressed("/tmp/phase3_hedging_arrays.npz", **arrays)
    summary = {}
    for key in outputs:
        pnl = arrays[f"{key}_pnl"]
        summary[key] = {
            "paths": len(pnl),
            "mean": float(pnl.mean()),
            "std": float(pnl.std(ddof=1)),
            "rmse": float(np.sqrt(np.mean(pnl**2))),
            "mean_trades": float(arrays[f"{key}_trades"].mean()),
            "mean_turnover": float(arrays[f"{key}_turnover"].mean()),
            "mean_costs": float(arrays[f"{key}_costs"].mean()),
            "mean_cost_impact": float(arrays[f"{key}_cost_impact"].mean()),
        }
    report = {
        "metadata": {
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "dirty": bool(
                subprocess.check_output(["git", "status", "--porcelain"], text=True)
            ),
            "seed": 20261122,
            "generator": "PCG64",
            "batch": 512,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "cpu": platform.processor(),
            "seconds": time.perf_counter() - started,
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024**2 if sys.platform == "darwin" else 1024),
            "reproduce": "python examples/hedging_research.py",
        },
        "summary": summary,
    }
    Path("/tmp/phase3_hedging_summary.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
