"""Check a default full run against the repository's frozen numerical evidence."""

import argparse
import json
from math import isclose
from pathlib import Path


def compare(actual, expected, location):
    """Match structure, exact discrete data and numerical tolerances."""
    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise ValueError(f"fields changed at {location}")
        for key in expected:
            compare(actual[key], expected[key], f"{location}.{key}")
    elif isinstance(expected, list):
        for index, (a, e) in enumerate(zip(actual, expected, strict=True)):
            compare(a, e, f"{location}[{index}]")
    elif isinstance(expected, float):
        if not isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9):
            raise ValueError(f"{location}: {actual} differs from {expected}")
    elif actual != expected:
        raise ValueError(f"{location}: discrete value changed")


def verify(run):
    frozen = Path(__file__).resolve().parents[1] / "docs/results"
    for name, file, sections in [
        ("mc", "phase2_mc_study", ("example", "grid", "convergence")),
        ("hedge", "phase3_hedging_summary", ("summary",)),
        ("risk", "phase4_risk", ("scenarios", "audit")),
    ]:
        current = json.loads((run / f"{name}.json").read_text())
        history = json.loads((frozen / f"{file}.json").read_text())
        for section in sections:
            compare(current[section], history[section], f"{name}.{section}")
    for kind, row in json.loads((run / "analytical.json").read_text()).items():
        if abs(row["price"] - row["integrated"]) > 1e-8 * 100:
            raise ValueError(f"{kind} quadrature mismatch")
        for greek in ("delta", "gamma", "vega", "theta", "rho"):
            ref = row["differences"][greek]
            if abs(row["greeks"][greek] - ref) > 1e-6 + 1e-4 * abs(ref):
                raise ValueError(f"{kind} {greek} differs from finite differences")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    verify(p.parse_args().run)
    print("Analytical checks and all frozen numerical sections passed.")
