"""Command-line entry point for the reproducible research workflows."""

import argparse
import json
import platform
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from . import EuropeanOption, MarketSnapshot, OptionType, greeks, price
from .experiments import run_study
from .hedging_study import run as hedge
from .risk_study import run as risk
from .validation import finite_difference_greeks, integrated_price


def analytical():
    """Evaluate the reference contract and both numerical benchmarks."""
    market = MarketSnapshot(100, 0.03, 0.01, 0.2)
    results = {}
    for kind in OptionType:
        option = EuropeanOption(kind, 100, 1, 100)
        results[kind.value] = dict(
            option=asdict(option),
            market=asdict(market),
            price=price(option, market),
            greeks=asdict(greeks(option, market)),
            integrated=integrated_price(option, market),
            differences=asdict(finite_difference_greeks(option, market)),
        )
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run European equity option research.")
    parser.add_argument("workflow", choices=["price", "mc", "hedge", "risk", "all"])
    parser.add_argument(
        "--mode",
        choices=["fast", "full"],
        default="fast",
        help="Fast validation or the historical research budgets",
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="New directory for results"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="JSON overrides: seed, bootstrap_seed, paths, repeats, replicates",
    )
    args = parser.parse_args(argv)
    fast = args.mode == "fast"
    cfg = dict(
        seed=20261122,
        bootstrap_seed=94781,
        paths=256 if fast else 10000,
        repeats=2 if fast else 100,
        replicates=20 if fast else 1000,
    )
    try:
        if args.config:
            values = json.loads(args.config.read_text())
            if not isinstance(values, dict) or values.keys() - cfg.keys():
                raise ValueError("unknown configuration keys or invalid JSON object")
            cfg.update(values)
        for key, value in cfg.items():
            if type(value) is not int or value < (0 if "seed" in key else 2):
                raise ValueError(f"invalid {key}")
        out = args.output.absolute()
        if out.exists():
            raise ValueError("output directory already exists")
        out.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=out.parent) as tmp:
            stage = Path(tmp) / "results"
            stage.mkdir()

            def save(name, data):
                (stage / f"{name}.json").write_text(
                    json.dumps(data, indent=2, allow_nan=False) + "\n"
                )

            save(
                "metadata",
                dict(
                    workflow=args.workflow,
                    mode=args.mode,
                    config=cfg,
                    desk_parameters=dict(
                        spot=100,
                        strike=100,
                        maturity_years=1,
                        multiplier=100,
                        rate=0.03,
                        dividend_yield=0,
                        physical_drift=0.05,
                        implied_volatility=0.20,
                        path_volatilities=[0.15, 0.20, 0.30],
                        trading_steps=252,
                        batch_size=512,
                        hedge_intervals=[1, 5],
                        cost_bps=[0, 1, 5, 10],
                        alpha=0.95,
                    ),
                    python=platform.python_version(),
                    versions={
                        k: version(k) for k in ("optionlab-analytics", "numpy", "scipy")
                    },
                ),
            )
            if args.workflow in ("price", "all"):
                save("analytical", analytical())
            if args.workflow in ("mc", "all"):
                save("mc", run_study(cfg["repeats"], not fast, root_seed=cfg["seed"]))
            if args.workflow in ("hedge", "all"):
                save("hedge", hedge(stage, cfg["paths"], cfg["seed"]))
            if args.workflow in ("risk", "all"):
                save(
                    "risk",
                    risk(
                        cfg["paths"],
                        cfg["seed"],
                        cfg["replicates"],
                        cfg["bootstrap_seed"],
                    ),
                )
            stage.rename(out)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
