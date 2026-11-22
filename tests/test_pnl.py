from dataclasses import replace

import numpy as np
import pytest

from optionlab import EuropeanOption, MarketSnapshot, OptionType, greeks, price
from optionlab.hedging import simulate_hedge
from optionlab.pnl import attribute, revalue

OPTION = EuropeanOption(OptionType.CALL, 100, 1, 100)
MARKET = MarketSnapshot(100, 0.03, 0.01, 0.2)


def test_ledger_explain():
    result = simulate_hedge(
        OPTION,
        MARKET,
        np.array([[100.0], [110.0], [85.0], [125.0]]),
        2,
        10,
        audit_path=0,
    )
    rows = attribute(OPTION, MARKET, result.ledger)
    assert sum(x["actual"] for x in rows) == pytest.approx(result.pnl[0])
    assert max(abs(x["exact_error"]) for x in rows) < 1e-9
    assert all(row["terms"]["vega"] == 0 for row in rows)
    assert rows[0]["actual"] == pytest.approx(-result.ledger[0]["fee"])
    assert rows[-1]["terms"]["fees"] == -result.ledger[-1]["fee"]
    assert rows[1]["terms"]["financing"] < 0 < rows[1]["terms"]["dividend"]
    assert rows[1]["terms"]["gamma"] < 0 < rows[1]["terms"]["theta"]
    assert abs(rows[-1]["residual"]) > 1
    assert rows[1]["terms"]["delta"] == pytest.approx(0, abs=1e-11)
    result.ledger[1]["equity"] += 1
    with pytest.raises(ValueError, match="reconciliation"):
        attribute(OPTION, MARKET, result.ledger)


@pytest.mark.parametrize("time", [0, 0.9999])
def test_static_full_reprice(time):
    m = replace(MARKET, time=time)
    g = greeks(OPTION, m)
    s = revalue(OPTION, m, 35, -200, 15, 0.04)
    expected = 35 * 15 - 100 * (
        price(OPTION, replace(m, spot=115, volatility=0.24)) - price(OPTION, m)
    )
    assert s["actual"] == pytest.approx(expected)
    assert s["terms"]["delta"] == pytest.approx((35 - 100 * g.delta) * 15)
    assert s["terms"]["vega"] == pytest.approx(-100 * g.vega * 0.04)
    assert s["terms"]["gamma"] == pytest.approx(-50 * g.gamma * 225)
    assert s["residual"] == pytest.approx(expected - sum(s["terms"].values()))
