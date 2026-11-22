"""Empirical contract-currency losses and path-paired sampling uncertainty."""

from collections.abc import Mapping
from math import ceil, floor

import numpy as np
from numpy.typing import ArrayLike

from ._validation import finite_real


def _sample(values: ArrayLike) -> np.ndarray:
    a = np.asarray(values)
    if a.ndim != 1 or not a.size or a.dtype.kind not in "ifu":
        raise ValueError("expected a nonempty real numeric vector")
    a = a.astype(float, copy=False)
    if not np.all(np.isfinite(a)):
        raise ValueError("sample must be finite")
    return a


def tail_risk(losses: ArrayLike, alpha: float = 0.95) -> dict:
    """Nearest-rank VaR and fractional upper-tail mean, including ties."""
    finite_real("alpha", alpha)
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    ordered = np.sort(_sample(losses))
    rank = ceil(len(ordered) * alpha)
    mass = len(ordered) * (1 - alpha)
    whole = floor(mass)
    tail_sum = ordered[len(ordered) - whole :].sum()
    if whole < len(ordered):
        tail_sum += (mass - whole) * ordered[-whole - 1]
    return dict(
        var=float(ordered[rank - 1]),
        es=float(tail_sum / mass),
        worst_observed=float(ordered[-1]),
        tail_mass=mass,
    )


def summarize(pnl: ArrayLike, alpha: float = 0.95) -> dict:
    """Summarize net terminal P&L, with losses equal to minus P&L."""
    x = _sample(pnl)
    if len(x) < 2:
        raise ValueError("sample SD requires two paths")
    return dict(
        mean=float(x.mean()),
        sd=float(x.std(ddof=1)),
        rmse=float(np.sqrt(np.mean(x * x))),
        **tail_risk(-x, alpha),
    )


def paired_bootstrap(
    daily: Mapping,
    weekly: Mapping,
    *,
    seed: int,
    replicates: int = 1000,
    alpha: float = 0.95,
) -> dict:
    """Daily minus weekly percentile intervals; mappings keyed by shared path ID."""
    if daily.keys() != weekly.keys():
        raise ValueError("strategy path IDs differ")
    if type(replicates) is not int or replicates < 2:
        raise ValueError("at least two bootstrap replicates required")
    ids = sorted(daily)
    d = _sample([daily[i] for i in ids])
    w = _sample([weekly[i] for i in ids])
    metrics = ("mean", "sd", "rmse", "var", "es")

    def difference(a, b):
        left, right = summarize(a, alpha), summarize(b, alpha)
        return [left[key] - right[key] for key in metrics]

    point = difference(d, w)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(replicates):
        index = rng.integers(len(ids), size=len(ids))
        draws.append(difference(d[index], w[index]))
    bounds = np.percentile(draws, [2.5, 97.5], axis=0)
    return {
        key: dict(point=point[i], low=float(bounds[0, i]), high=float(bounds[1, i]))
        for i, key in enumerate(metrics)
    }
