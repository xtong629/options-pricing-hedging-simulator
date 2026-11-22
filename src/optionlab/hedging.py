"""Discrete self-financing hedge of one short European call."""

from dataclasses import dataclass, replace
from math import exp, isfinite

import numpy as np
from numpy.typing import NDArray
from scipy.special import ndtr

from .instruments import EuropeanOption, OptionType
from .market import MarketSnapshot
from .pricing import price


@dataclass(frozen=True)
class HedgeResult:
    """Per-path final cash, turnover, costs and optional audit rows."""

    pnl: NDArray[np.float64]
    turnover: NDArray[np.float64]
    costs: NDArray[np.float64]
    trades: NDArray[np.int64]
    cost_impact: NDArray[np.float64]
    ledger: list[dict]


def physical_paths(
    spot: float,
    mu: float,
    q: float,
    volatility: float,
    dt: float,
    normals: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Generate P-measure paths; normals have shape (steps, paths)."""
    z = np.asarray(normals, dtype=float)
    if z.ndim != 2 or not np.all(np.isfinite(z)):
        raise ValueError("normals must be a finite two-dimensional array")
    if not all(isfinite(x) for x in (spot, mu, q, volatility, dt)):
        raise ValueError("parameters must be finite")
    if spot <= 0 or volatility < 0 or dt <= 0:
        raise ValueError("spot and dt must be positive, volatility nonnegative")
    with np.errstate(over="raise", invalid="raise"):
        increments = (mu - q - volatility**2 / 2) * dt + volatility * np.sqrt(dt) * z
        paths = np.vstack(
            (np.full(z.shape[1], spot), spot * np.exp(np.cumsum(increments, axis=0)))
        )
    if not np.all(np.isfinite(paths)) or np.any(paths <= 0):
        raise ValueError("path values outside floating point range")
    return paths


def simulate_hedge(
    option: EuropeanOption,
    market: MarketSnapshot,
    paths: NDArray[np.float64],
    rebalance_every: int = 1,
    cost_bps: float = 0,
    substeps_per_day: int = 1,
    audit_path: int | None = None,
) -> HedgeResult:
    """Evaluate paths, with rows at every cash-flow step for one selected path.

    Paths include initial and final spot. Rebalancing occurs at multiples of
    rebalance_every base days; substeps refine the cash/dividend grid.
    """
    spots = np.asarray(paths, dtype=float)
    if option.option_type != OptionType.CALL:
        raise ValueError("only short calls are supported")
    if spots.ndim != 2 or spots.shape[0] < 2 or spots.shape[1] < 1:
        raise ValueError("paths must contain at least one interval and one path")
    if not np.all(np.isfinite(spots)) or np.any(spots <= 0):
        raise ValueError("all spots must be finite and positive")
    if not np.allclose(spots[0], market.spot, rtol=1e-12, atol=0):
        raise ValueError("initial paths must equal market spot")
    if market.volatility <= 0 or option.maturity <= market.time:
        raise ValueError("positive implied volatility and remaining time required")
    for value in (rebalance_every, substeps_per_day):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("frequency and substeps must be positive integers")
    if not isfinite(cost_bps) or cost_bps < 0:
        raise ValueError("cost_bps must be finite and nonnegative")
    if audit_path is not None and (
        not isinstance(audit_path, int) or not 0 <= audit_path < spots.shape[1]
    ):
        raise ValueError("audit_path is out of range")
    n_steps = spots.shape[0] - 1
    if n_steps % substeps_per_day:
        raise ValueError("intervals must contain whole base days")
    dt = (option.maturity - market.time) / n_steps
    count = spots.shape[1]
    premium = price(option, market) * option.multiplier
    cash = np.full(count, premium)
    shares = np.zeros(count)
    turnover = np.zeros(count)
    costs = np.zeros(count)
    trade_count = np.zeros(count, dtype=np.int64)
    impact = np.zeros(count)
    rows = []
    frequency = rebalance_every * substeps_per_day

    for i in range(n_steps + 1):
        spot = spots[i]
        interest = np.zeros(count)
        dividend = np.zeros(count)
        if i:
            interest = cash * (exp(market.rate * dt) - 1)
            dividend = shares * market.dividend_yield * spots[i - 1] * dt
            cash += interest + dividend
            impact *= exp(market.rate * dt)
        tau = (n_steps - i) * dt
        if i == n_steps:
            mark = np.maximum(spot - option.strike, 0)
            delta = np.full(count, np.nan)
        else:
            d1 = (
                np.log(spot / option.strike)
                + (market.rate - market.dividend_yield + market.volatility**2 / 2) * tau
            ) / (market.volatility * np.sqrt(tau))
            delta = np.exp(-market.dividend_yield * tau) * ndtr(d1)
            # Marks are only needed for an audit row.
            mark = None
        liability = option.multiplier * mark if mark is not None else None
        if audit_path is not None and mark is None:
            selected_market = replace(
                market, spot=float(spot[audit_path]), time=market.time + i * dt
            )
            liability = option.multiplier * price(option, selected_market)
        before = shares.copy()
        target = shares.copy()
        if i == n_steps:
            target = np.zeros(count)
        elif i % frequency == 0:
            target = option.multiplier * delta
        change = target - shares
        value = np.abs(change) * spot
        fee = cost_bps * 1e-4 * value
        cash -= change * spot + fee
        shares = target
        turnover += value
        costs += fee
        trade_count += change != 0
        impact += fee
        if audit_path is not None:
            k = audit_path
            selected_liability = float(
                liability[k] if isinstance(liability, np.ndarray) else liability
            )
            rows.append(
                {
                    "step": i,
                    "time": market.time + i * dt,
                    "path_id": k,
                    "spot": float(spot[k]),
                    "option_mark": selected_liability / option.multiplier,
                    "liability": selected_liability,
                    "delta": None if i == n_steps else float(delta[k]),
                    "target": float(target[k]),
                    "shares_before": float(before[k]),
                    "shares_after": float(shares[k]),
                    "shares_traded": float(change[k]),
                    "interest": float(interest[k]),
                    "dividend": float(dividend[k]),
                    "fee": float(fee[k]),
                    "cash": float(cash[k]),
                    "stock_value": float(shares[k] * spot[k]),
                    "equity": float(cash[k] + shares[k] * spot[k] - selected_liability),
                    "settlement": float(selected_liability) if i == n_steps else 0.0,
                    "premium": premium if i == 0 else 0.0,
                }
            )
        if i == n_steps:
            cash -= liability
            if audit_path is not None:
                rows[-1]["cash_after_settlement"] = float(cash[audit_path])
    return HedgeResult(cash, turnover, costs, trade_count, impact, rows)
