"""Independent checks for stock trades and financing."""

from math import exp

import pytest

from optionlab.portfolio import PortfolioState


def test_cash_trade_and_equity_at_same_market_time():
    state = PortfolioState(cash=500)
    before = state.equity(100, 500)
    quantity, fee = state.trade(6, 100, 0.001)
    assert quantity == 6
    assert fee == pytest.approx(0.6)
    assert state.cash == pytest.approx(-100.6)
    assert state.equity(100, 500) - before == pytest.approx(-fee)
    before = state.equity(100, 500)
    quantity, fee = state.trade(2, 100, 0.001)
    assert quantity == -4
    assert state.cash == pytest.approx(299)
    assert state.equity(100, 500) - before == pytest.approx(-fee)


def test_accrual_negative_cash_and_dividends():
    state = PortfolioState(cash=-100, shares=5)
    interest, dividend = state.accrue(110, 0.03, 0.02, 0.5)
    assert interest == pytest.approx(-100 * (exp(0.015) - 1))
    assert dividend == pytest.approx(5.5)
    assert state.cash == pytest.approx(-100 + interest + dividend)
