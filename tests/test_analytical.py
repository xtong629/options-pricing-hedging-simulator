"""Mathematical properties, independent integration and derivative validation."""

from dataclasses import replace
from itertools import product
from math import exp, isfinite

import pytest

from optionlab import EuropeanOption, MarketSnapshot, OptionType, greeks, price
from optionlab.validation import finite_difference_greeks, integrated_price

CASES = list(product((80.0, 100.0, 120.0), (0.25, 1.0), (0.15, 0.3), (-0.02, 0.03)))


@pytest.mark.parametrize("strike,tenor,vol,rate", CASES)
@pytest.mark.parametrize("kind", list(OptionType))
def test_independent_integration_and_bounds(strike, tenor, vol, rate, kind):
    option = EuropeanOption(kind, strike, tenor)
    market = MarketSnapshot(100, rate, 0.01, vol)
    actual = price(option, market)
    reference = integrated_price(option, market)
    assert abs(actual - reference) <= 1e-8 * max(1, strike, market.spot)
    a = market.spot * exp(-market.dividend_yield * tenor)
    b = strike * exp(-rate * tenor)
    intrinsic, upper = (a - b, a) if kind == OptionType.CALL else (b - a, b)
    assert max(intrinsic, 0) - 1e-12 <= actual <= upper + 1e-12


@pytest.mark.parametrize("strike,tenor,vol,rate", CASES)
def test_parity(strike, tenor, vol, rate):
    call = EuropeanOption(OptionType.CALL, strike, tenor)
    put = replace(call, option_type=OptionType.PUT)
    market = MarketSnapshot(100, rate, 0.01, vol)
    residual = price(call, market) - price(put, market)
    expected = 100 * exp(-0.01 * tenor) - strike * exp(-rate * tenor)
    assert residual == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("kind", list(OptionType))
@pytest.mark.parametrize("strike,tenor,vol,rate", CASES)
@pytest.mark.parametrize("bump", (1e-3, 1e-4, 1e-5))
def test_all_greeks_against_central_differences(kind, strike, tenor, vol, rate, bump):
    option = EuropeanOption(kind, strike, tenor)
    market = MarketSnapshot(100, rate, 0.01, vol, time=0.1)
    actual = greeks(option, market)
    numeric = finite_difference_greeks(option, market, bump)
    for field in ("delta", "gamma", "vega", "theta", "rho"):
        reference = getattr(numeric, field)
        assert abs(getattr(actual, field) - reference) <= 1e-6 + 1e-4 * abs(reference)


@pytest.mark.parametrize("kind", list(OptionType))
def test_monotonicity(kind):
    market = MarketSnapshot(100, -0.02, 0.03, 0.2)
    option = EuropeanOption(kind, 100, 1)
    strikes = [price(replace(option, strike=k), market) for k in (80, 100, 120)]
    spots = [price(option, replace(market, spot=s)) for s in (80, 100, 120)]
    assert strikes == sorted(strikes, reverse=kind == OptionType.CALL)
    assert spots == sorted(spots, reverse=kind == OptionType.PUT)


@pytest.mark.parametrize("kind", list(OptionType))
@pytest.mark.parametrize("spot", (50, 100, 150))
@pytest.mark.parametrize(
    "tenor,vol,status", ((0, 0.2, "expiry"), (1, 0, "zero_volatility"))
)
def test_boundaries(kind, spot, tenor, vol, status):
    option = EuropeanOption(kind, 100, tenor)
    market = MarketSnapshot(spot, -0.02, 0.01, vol)
    eta = 1 if kind == OptionType.CALL else -1
    expected = max(eta * (spot * exp(-0.01 * tenor) - 100 * exp(0.02 * tenor)), 0)
    assert price(option, market) == pytest.approx(expected, abs=1e-12)
    result = greeks(option, market)
    assert result.status == status
    assert all(
        getattr(result, f) is None for f in ("delta", "gamma", "vega", "theta", "rho")
    )


@pytest.mark.parametrize("kind", list(OptionType))
@pytest.mark.parametrize("spot", (1, 100, 10000))
def test_small_tenor_and_tail(kind, spot):
    option = EuropeanOption(kind, 100, 1e-10)
    market = MarketSnapshot(spot, -0.02, 0.01, 0.2)
    assert price(option, market) >= 0
    assert all(
        isfinite(getattr(greeks(option, market), f))
        for f in ("delta", "gamma", "vega", "theta", "rho")
    )
    assert price(option, market) == pytest.approx(
        max((spot - 100) * (1 if kind == OptionType.CALL else -1), 0), abs=1e-4
    )


@pytest.mark.parametrize("kind", list(OptionType))
def test_deterministic_limit_and_multiplier(kind):
    option = EuropeanOption(kind, 110, 1, multiplier=100)
    market = MarketSnapshot(100, -0.02, 0.01, 1e-8)
    assert price(option, market) == pytest.approx(
        price(option, replace(market, volatility=0))
    )
    assert price(option, market) == price(replace(option, multiplier=1), market)
    assert greeks(option, market) == greeks(replace(option, multiplier=1), market)


@pytest.mark.parametrize(
    "bad", (float("nan"), float("inf"), -float("inf"), True, "1", None)
)
@pytest.mark.parametrize(
    "field", ("spot", "rate", "dividend_yield", "volatility", "time")
)
def test_invalid_market(field, bad):
    with pytest.raises((ValueError, TypeError)):
        replace(MarketSnapshot(100, 0.03, 0.01, 0.2), **{field: bad})


@pytest.mark.parametrize("field", ("strike", "maturity", "multiplier"))
@pytest.mark.parametrize("bad", (float("nan"), float("inf"), True, "1", None))
def test_invalid_contract(field, bad):
    with pytest.raises((ValueError, TypeError)):
        replace(EuropeanOption(OptionType.CALL, 100, 1), **{field: bad})


@pytest.mark.parametrize(
    "field,value", (("spot", 0), ("spot", -1), ("volatility", -1), ("time", -1))
)
def test_negative_market(field, value):
    with pytest.raises(ValueError):
        replace(MarketSnapshot(100, 0.03, 0.01, 0.2), **{field: value})


@pytest.mark.parametrize(
    "field,value",
    (
        ("strike", 0),
        ("strike", -1),
        ("maturity", -1),
        ("multiplier", 0),
        ("multiplier", -1),
    ),
)
def test_invalid_contract_ranges(field, value):
    with pytest.raises(ValueError):
        replace(EuropeanOption(OptionType.CALL, 100, 1), **{field: value})


def test_type_clock_and_overflow():
    with pytest.raises(TypeError):
        EuropeanOption("call", 100, 1)
    option = EuropeanOption(OptionType.CALL, 100, 1)
    expired = MarketSnapshot(100, 0, 0, 0.2, time=2)
    for function in (price, greeks):
        with pytest.raises(ValueError):
            function(option, expired)
        with pytest.raises(ValueError, match="floating-point"):
            function(option, MarketSnapshot(100, 0, -1000, 0.2))


@pytest.mark.parametrize("q", (0.0, 0.05, -0.01))
def test_dividend_greek_relations(q):
    market = MarketSnapshot(100, -0.02, q, 0.2)
    call = EuropeanOption(OptionType.CALL, 100, 1)
    put = replace(call, option_type=OptionType.PUT)
    c, p = greeks(call, market), greeks(put, market)
    assert c.delta - p.delta == pytest.approx(exp(-q))
    assert c.gamma == p.gamma
    assert c.vega == p.vega
    assert c.rho - p.rho == pytest.approx(100 * exp(0.02))
    assert c.theta - p.theta == pytest.approx(q * 100 * exp(-q) + 2 * exp(0.02))
    assert c.delta > 0 and p.delta < 0
    assert c.gamma > 0 and c.vega > 0
    assert c.rho > 0 and p.rho < 0


@pytest.mark.parametrize("kind,spot", ((OptionType.CALL, 50), (OptionType.PUT, 200)))
def test_otm_tail_relative_accuracy(kind, spot):
    option = EuropeanOption(kind, 100, 1)
    market = MarketSnapshot(spot, 0.03, 0, 0.2)
    reference = integrated_price(option, market)
    assert reference > 0
    assert price(option, market) == pytest.approx(reference, rel=1e-9, abs=1e-15)
