"""Run from the repository root: python examples/risk_research.py OUTPUT.json."""

import platform
import resource
import sys
from collections import defaultdict
from time import perf_counter

import numpy as np
import scipy

from optionlab import EuropeanOption, MarketSnapshot, OptionType
from optionlab.hedging import physical_paths, simulate_hedge
from optionlab.pnl import attribute, revalue
from optionlab.risk import paired_bootstrap, summarize

from .provenance import source_revision


def run(n_paths=10000, seed=20261122, replicates=1000, bootstrap_seed=94781):
    start = perf_counter()
    o = EuropeanOption(OptionType.CALL, 100, 1, 100)
    m = MarketSnapshot(100, 0.03, 0, 0.2)
    rng = np.random.default_rng(seed)
    scenarios = []
    audit = {}
    for vol in (0.15, 0.2, 0.3):
        terminal = defaultdict(dict)
        for offset in range(0, n_paths, 512):
            size = min(512, n_paths - offset)
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
                    bootstrap=paired_bootstrap(
                        daily, weekly, seed=bootstrap_seed, replicates=replicates
                    ),
                )
            )
    return dict(
        source=source_revision(),
        python=platform.python_version(),
        numpy=np.__version__,
        scipy=scipy.__version__,
        platform=platform.platform(),
        seconds=perf_counter() - start,
        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
        scenarios=scenarios,
        audit=audit,
        paths=n_paths,
        replicates=replicates,
        bootstrap_seed=bootstrap_seed,
        path_seed=seed,
    )
