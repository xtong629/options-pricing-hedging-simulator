"""Scalar Black-Scholes-Merton valuation with continuous dividend yield."""

from math import exp, expm1, isfinite, log, sqrt

from scipy.special import log_ndtr

from .instruments import EuropeanOption, OptionType
from .market import MarketSnapshot


def _terms(option: EuropeanOption, market: MarketSnapshot) -> tuple[float, ...]:
    """Validate the joint clock and return discounted log values and d terms."""
    tau = option.maturity - market.time
    if tau < 0:
        raise ValueError("market time must not exceed maturity")
    log_a = log(market.spot) - market.dividend_yield * tau
    log_b = log(option.strike) - market.rate * tau
    width = market.volatility * sqrt(tau)
    if width == 0:
        return tau, log_a, log_b, 0.0, 0.0
    d1 = (log_a - log_b) / width + width / 2
    return tau, log_a, log_b, d1, d1 - width


def _positive_difference(log_x: float, log_y: float) -> float:
    """Evaluate exp(log_x)-exp(log_y) without subtracting nearly equal values."""
    if log_x <= log_y:
        return 0.0
    return exp(log_x) * -expm1(log_y - log_x)


def price(option: EuropeanOption, market: MarketSnapshot) -> float:
    """Return long per-share value in spot currency.

    Expiry returns intrinsic value. Zero volatility returns discounted
    deterministic payoff. Values outside float64 representability raise
    ValueError; tiny tail values may underflow to zero.
    """
    tau, log_a, log_b, d1, d2 = _terms(option, market)
    try:
        if tau == 0 or market.volatility == 0:
            if option.option_type == OptionType.CALL:
                result = _positive_difference(log_a, log_b)
            else:
                result = _positive_difference(log_b, log_a)
        elif log_a <= log_b:
            call = _positive_difference(
                log_a + float(log_ndtr(d1)), log_b + float(log_ndtr(d2))
            )
            result = call
            if option.option_type == OptionType.PUT:
                result += _positive_difference(log_b, log_a)
        else:
            put = _positive_difference(
                log_b + float(log_ndtr(-d2)), log_a + float(log_ndtr(-d1))
            )
            result = put
            if option.option_type == OptionType.CALL:
                result += _positive_difference(log_a, log_b)
    except OverflowError as error:
        raise ValueError("price exceeds floating-point range") from error
    if not isfinite(result):
        raise ValueError("price exceeds floating-point range")
    return result
