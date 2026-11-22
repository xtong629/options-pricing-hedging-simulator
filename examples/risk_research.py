"""Run from the repository root: python examples/risk_research.py OUTPUT.json."""

import json
import platform
import resource
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from time import perf_counter

import numpy as np
import scipy

from optionlab import EuropeanOption, MarketSnapshot, OptionType
from optionlab.hedging import physical_paths, simulate_hedge
from optionlab.pnl import attribute, revalue
from optionlab.risk import paired_bootstrap, summarize


def run():
    start = perf_counter()
    o = EuropeanOption(OptionType.CALL, 100, 1, 100)
    m = MarketSnapshot(100, 0.03, 0, 0.2)
    rng = np.random.default_rng(20261122)
    scenarios = []
    audit = {}
    for vol in (0.15, 0.2, 0.3):
        terminal = defaultdict(dict)
        for offset in range(0, 10000, 512):
            size = min(512, 10000 - offset)
            paths = physical_paths(
                100, 0.05, 0, vol, 1 / 252, rng.standard_normal((252, size))
            )
            for freq in (1, 5):
                for cost in (0, 1, 5, 10):
                    selected = vol == 0.2 and freq == 5 and cost == 5 and offset == 0
                    result = simulate_hedge(
                        o, m, paths, freq, cost, audit_path=0 if selected else None
                    )
                    terminal[freq, cost].update(
                        zip(range(offset, offset + size), result.pnl, strict=True)
                    )
                    if selected:
                        audit["ledger"] = result.ledger
                        audit["explain"] = attribute(o, m, result.ledger)
                        initial = result.ledger[0]
                        audit["static"] = [
                            revalue(
                                o, m, initial["shares_after"], initial["cash"], ds, dv
                            )
                            for ds, dv in [
                                (1, 0),
                                (10, 0),
                                (-10, 0),
                                (0, 0.05),
                                (10, 0.05),
                            ]
                        ]
        for cost in (0, 1, 5, 10):
            daily, weekly = terminal[1, cost], terminal[5, cost]
            scenarios.append(
                dict(
                    vol=vol,
                    bps=cost,
                    daily=summarize(list(daily.values())),
                    weekly=summarize(list(weekly.values())),
                    bootstrap=paired_bootstrap(daily, weekly, seed=94781),
                )
            )
    return dict(
        source=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        python=platform.python_version(),
        numpy=np.__version__,
        scipy=scipy.__version__,
        platform=platform.platform(),
        seconds=perf_counter() - start,
        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
        scenarios=scenarios,
        audit=audit,
        paths=10000,
        replicates=1000,
        bootstrap_seed=94781,
        path_seed=20261122,
    )


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(run(), allow_nan=False, indent=2) + "\n")
