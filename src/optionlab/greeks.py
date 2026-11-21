"""Analytical long per-share sensitivities."""

from dataclasses import dataclass
from math import exp, isfinite, pi, sqrt
from typing import Literal

from scipy.special import ndtr

from .instruments import EuropeanOption, OptionType
from .market import MarketSnapshot
from .pricing import _terms


@dataclass(frozen=True)
class GreeksResult:
    """Annual, absolute-input derivatives; boundary Greeks are missing.

    Theta is calendar-time decay per year. Vega/rho are per unit volatility/rate.
    Multiply by .01/.0001 for a vol point/bp and divide theta by 252 for a day.
    """

    delta: float | None
    gamma: float | None
    vega: float | None
    theta: float | None
    rho: float | None
    status: Literal["regular", "expiry", "zero_volatility"] = "regular"


def greeks(option: EuropeanOption, market: MarketSnapshot) -> GreeksResult:
    """Return per-share long Greeks, or explicit missing values at boundaries."""
    tau, log_a, log_b, d1, d2 = _terms(option, market)
    if tau == 0:
        return GreeksResult(None, None, None, None, None, "expiry")
    if market.volatility == 0:
        return GreeksResult(None, None, None, None, None, "zero_volatility")
    eta = 1 if option.option_type == OptionType.CALL else -1
    try:
        a, b = exp(log_a), exp(log_b)
        discount = exp(-market.dividend_yield * tau)
        density = exp(-d1 * d1 / 2) / sqrt(2 * pi)
        n1, n2 = float(ndtr(eta * d1)), float(ndtr(eta * d2))
        delta = eta * discount * n1
        gamma = discount * density / (market.spot * market.volatility * sqrt(tau))
        vega = a * density * sqrt(tau)
        theta = -a * density * market.volatility / (2 * sqrt(tau)) + eta * (
            market.dividend_yield * a * n1 - market.rate * b * n2
        )
        rho = eta * tau * b * n2
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError("Greeks exceed floating-point range") from error
    if not all(isfinite(x) for x in (delta, gamma, vega, theta, rho)):
        raise ValueError("Greeks exceed floating-point range")
    return GreeksResult(delta, gamma, vega, theta, rho)
