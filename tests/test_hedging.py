"""Cash-flow identities, causal schedules and P-path validation."""

from math import exp

import numpy as np
import pytest

from optionlab import EuropeanOption, MarketSnapshot, OptionType, greeks, price
from optionlab.hedging import physical_paths, simulate_hedge

OPTION = EuropeanOption(OptionType.CALL, 100, 1, 100)
MARKET = MarketSnapshot(100, 0.03, 0.01, 0.2)


def test_two_step_cash_ledger_and_terminal_settlement():
    paths = np.array([[100.0], [110.0], [90.0]])
    result = simulate_hedge(OPTION, MARKET, paths, cost_bps=10, audit_path=0)
    a, b, c = result.ledger
    delta0 = greeks(OPTION, MARKET).delta * 100
    premium = price(OPTION, MARKET) * 100
    fee0 = delta0 * 100 * 0.001
    assert a["premium"] == pytest.approx(premium)
    assert a["shares_after"] == pytest.approx(delta0)
    assert a["cash"] == pytest.approx(premium - delta0 * 100 - fee0)
    assert a["equity"] == pytest.approx(-fee0)
    cash_before = a["cash"] * exp(0.03 / 2) + delta0 * 0.01 * 100 / 2
    delta1 = greeks(OPTION, MarketSnapshot(110, 0.03, 0.01, 0.2, 0.5)).delta * 100
    trade1 = delta1 - delta0
    fee1 = abs(trade1) * 110 * 0.001
    assert b["cash"] == pytest.approx(cash_before - trade1 * 110 - fee1)
    assert b["shares_after"] == pytest.approx(delta1)
    cash2 = b["cash"] * exp(0.03 / 2) + delta1 * 0.01 * 110 / 2
    assert c["cash_after_settlement"] == pytest.approx(
        cash2 + delta1 * 90 - delta1 * 90 * 0.001
    )
    assert c["shares_after"] == 0
    assert c["settlement"] == 0
    assert result.pnl[0] == pytest.approx(c["cash_after_settlement"])
    for previous, current in zip(result.ledger, result.ledger[1:]):
        expected = (
            previous["equity"]
            + previous["shares_after"] * (current["spot"] - previous["spot"])
            - (current["liability"] - previous["liability"])
            + current["interest"]
            + current["dividend"]
            - current["fee"]
        )
        assert current["equity"] == pytest.approx(expected, abs=1e-9)


def test_expiry_in_the_money_and_financed_cost_difference():
    paths = np.array([[100.0], [95.0], [120.0]])
    gross = simulate_hedge(OPTION, MARKET, paths, cost_bps=0)
    net = simulate_hedge(OPTION, MARKET, paths, cost_bps=5, audit_path=0)
    assert net.ledger[-1]["settlement"] == 2000
    assert net.pnl[0] == pytest.approx(net.ledger[-1]["cash_after_settlement"])
    assert gross.pnl[0] - net.pnl[0] == pytest.approx(net.cost_impact[0], abs=1e-9)
    fees = [row["fee"] for row in net.ledger]
    assert net.cost_impact[0] == pytest.approx(
        fees[0] * exp(0.03) + fees[1] * exp(0.015) + fees[2]
    )


def test_weekly_schedule_incomplete_week_and_no_lookahead():
    paths = np.array([[100 + i] for i in range(9)], dtype=float)
    a = simulate_hedge(OPTION, MARKET, paths, rebalance_every=5, audit_path=0)
    assert [r["step"] for r in a.ledger if r["shares_traded"] != 0] == [0, 5, 8]
    changed = paths.copy()
    changed[6:] *= 1.2
    b = simulate_hedge(OPTION, MARKET, changed, rebalance_every=5, audit_path=0)
    assert a.ledger[:6] == b.ledger[:6]


def test_physical_path_reproducibility_and_daily_weekly_same_path():
    z = np.random.default_rng(123).normal(size=(10, 4))
    paths = physical_paths(100, 0.05, 0.01, 0.2, 0.1, z)
    assert np.array_equal(paths, physical_paths(100, 0.05, 0.01, 0.2, 0.1, z))
    daily = simulate_hedge(OPTION, MARKET, paths, 1)
    weekly = simulate_hedge(OPTION, MARKET, paths, 5)
    assert len(daily.pnl) == len(weekly.pnl) == 4
    assert np.all(daily.trades >= weekly.trades)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        simulate_hedge(OPTION, MARKET, np.array([[100], [100]]), cost_bps=-1)
    with pytest.raises(ValueError):
        physical_paths(100, 0.05, 0, -0.1, 1, np.zeros((1, 1)))


def test_dividend_grid_convergence_with_coupled_paths():
    rng = np.random.default_rng(457)
    fine_z = rng.normal(size=(1008, 256))
    grids = []
    holdings = []
    results = []
    for factor in (1, 2, 4):
        group = 4 // factor
        z = fine_z.reshape(252 * factor, group, 256).sum(axis=1) / np.sqrt(group)
        paths = physical_paths(100, 0.05, 0.04, 0.2, 1 / (252 * factor), z)
        grids.append(paths[::factor])
        result = simulate_hedge(
            OPTION,
            MarketSnapshot(100, 0.03, 0.04, 0.2),
            paths,
            rebalance_every=5,
            substeps_per_day=factor,
        )
        results.append(result.pnl)
        holdings.append(result.trades)
    assert np.allclose(grids[0], grids[1], atol=1e-11)
    assert np.allclose(grids[1], grids[2], atol=1e-11)
    assert np.array_equal(holdings[0], holdings[1])
    assert np.array_equal(holdings[1], holdings[2])
    rms_coarse = np.sqrt(np.mean((results[0] - results[1]) ** 2))
    rms_fine = np.sqrt(np.mean((results[1] - results[2]) ** 2))
    assert rms_fine < rms_coarse


def test_deterministic_dividend_integration():
    from optionlab.portfolio import PortfolioState

    r, q, mu, h_shares = 0.03, 0.04, 0.05, 10
    exact = h_shares * q * 100 * exp(r) * (exp((mu - q - r)) - 1) / (mu - q - r)
    errors = []
    for n in (252, 504, 1008):
        state = PortfolioState(shares=h_shares)
        for i in range(n):
            spot = 100 * exp((mu - q) * i / n)
            state.accrue(spot, r, q, 1 / n)
        errors.append(abs(state.cash - exact))
    assert errors[2] < errors[1] < errors[0]
    assert errors[-1] < 1e-4 * 1000
