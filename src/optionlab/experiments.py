"""Reproducible terminal valuation and multi-seed convergence study.

Run python -m optionlab.experiments --output /tmp/mc-study.json.
"""

import argparse
import json
import platform
import resource
import subprocess
import sys
from dataclasses import asdict
from itertools import product
from pathlib import Path
from time import perf_counter

import numpy as np
import scipy

from .instruments import EuropeanOption, OptionType
from .market import MarketSnapshot
from .pricing import price
from .simulation import MonteCarloConfig, mc_price


def run_study(repeats: int = 100, full_grid: bool = False) -> dict:
    """Compare equal path budgets with independently spawned PCG64 streams."""
    if repeats < 2:
        raise ValueError("at least two seed repetitions are required")
    started = perf_counter()
    root_seed = 20261122
    batch_size = 4096
    market = MarketSnapshot(100, 0.03, 0.01, 0.2)
    example = []
    for kind, method in product(OptionType, ("standard", "antithetic")):
        option = EuropeanOption(kind, 100, 1, multiplier=100)
        config = MonteCarloConfig(100_000, method, root_seed, batch_size)
        value = mc_price(option, market, config)
        example.append(
            {
                "option": asdict(option),
                "market": asdict(market),
                "analytical_price": price(option, market),
                "result": asdict(value),
                "absolute_error": abs(value.estimate - price(option, market)),
            }
        )
    # Each (kind, method, N, repetition) receives its own spawned child stream.
    sequences = iter(np.random.SeedSequence(root_seed).spawn(2 * 2 * 3 * repeats))
    convergence = []
    for kind, method in product(OptionType, ("standard", "antithetic")):
        option = EuropeanOption(kind, 100, 1)
        analytical = price(option, market)
        rmse_values = []
        for n_paths in (1000, 10_000, 100_000):
            errors, ses, covered = [], [], []
            for _ in range(repeats):
                seed = int(next(sequences).generate_state(1, dtype=np.uint64)[0])
                value = mc_price(
                    option, market, MonteCarloConfig(n_paths, method, seed, batch_size)
                )
                errors.append(value.estimate - analytical)
                ses.append(value.standard_error)
                low, high = value.confidence_interval
                covered.append(low <= analytical <= high)
            rmse = float(np.sqrt(np.mean(np.square(errors))))
            rmse_values.append(rmse)
            coverage = float(np.mean(covered))
            convergence.append(
                {
                    "kind": kind.value,
                    "method": method,
                    "n_paths": n_paths,
                    "n_observations": n_paths // 2
                    if method == "antithetic"
                    else n_paths,
                    "repeats": repeats,
                    "rmse": rmse,
                    "mean_absolute_error": float(np.mean(np.abs(errors))),
                    "mean_standard_error": float(np.mean(ses)),
                    "mean_squared_standard_error": float(np.mean(np.square(ses))),
                    "coverage": coverage,
                    "coverage_sampling_se": float(
                        np.sqrt(coverage * (1 - coverage) / repeats)
                    ),
                }
            )
        slope = float(
            np.polyfit(np.log([1000, 10_000, 100_000]), np.log(rmse_values), 1)[0]
        )
        for row in convergence[-3:]:
            row["empirical_log_rmse_slope"] = slope
    for row in convergence:
        standard = next(
            x
            for x in convergence
            if x["kind"] == row["kind"]
            and x["n_paths"] == row["n_paths"]
            and x["method"] == "standard"
        )
        row["empirical_mse_ratio_to_standard"] = (
            row["rmse"] ** 2 / standard["rmse"] ** 2
        )
        row["estimated_variance_ratio_to_standard"] = (
            row["mean_squared_standard_error"] / standard["mean_squared_standard_error"]
        )
    grid = []
    if full_grid:
        sequences = iter(np.random.SeedSequence([root_seed, 24]).spawn(48))
        for kind, strike, tenor, vol, method in product(
            OptionType,
            (90, 100, 110),
            (0.25, 1),
            (0.15, 0.30),
            ("standard", "antithetic"),
        ):
            option = EuropeanOption(kind, strike, tenor)
            observation = MarketSnapshot(100, 0.03, 0.01, vol)
            seed = int(next(sequences).generate_state(1, dtype=np.uint64)[0])
            value = mc_price(
                option, observation, MonteCarloConfig(100_000, method, seed)
            )
            grid.append(
                {
                    "option": asdict(option),
                    "market": asdict(observation),
                    "analytical_price": price(option, observation),
                    "result": asdict(value),
                    "absolute_error": abs(value.estimate - price(option, observation)),
                }
            )
    # Git is optional when the installed wheel is run outside a checkout.
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
    )
    return {
        "metadata": {
            "source_commit": revision.stdout.strip() or None,
            "working_tree_dirty": bool(status.stdout.strip()),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "rng": "PCG64",
            "root_seed": root_seed,
            "batch_size_observations": batch_size,
            "repeats": repeats,
            "elapsed_seconds": perf_counter() - started,
            "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024**2 if sys.platform == "darwin" else 1024),
            "reproduction": (
                f"python -m optionlab.experiments --repeats {repeats}"
                + (" --full-grid" if full_grid else "")
                + " --output /tmp/mc-study.json"
            ),
        },
        "example": example,
        "convergence": convergence,
        "grid": grid,
    }


def main() -> None:
    """Write a compact JSON research artifact or print to stdout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--full-grid", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(
        run_study(args.repeats, args.full_grid), indent=2, allow_nan=False
    )
    if args.output:
        args.output.write_text(report + "\n")
    else:
        print(report)


if __name__ == "__main__":
    main()
