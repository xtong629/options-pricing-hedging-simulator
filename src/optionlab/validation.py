"""Independent deterministic numerical references, outside the pricing path."""

from dataclasses import replace
from math import exp, log, pi, sqrt

from scipy.integrate import quad

from .greeks import GreeksResult
from .instruments import EuropeanOption, OptionType
from .market import MarketSnapshot
from .pricing import price


def integrated_price(option: EuropeanOption, market: MarketSnapshot) -> float:
    """Integrate discounted payoff against a standard normal density.

    Intended for moderate positive volatility/tenor validation cases.
    The integrand uses GBM terminal payoff, without analytical pricing terms.
    """
    tau = option.maturity - market.time
    if tau <= 0 or market.volatility <= 0:
        raise ValueError("integration requires positive remaining tenor and volatility")
    width = market.volatility * sqrt(tau)
    mean = (
        log(market.spot)
        + (market.rate - market.dividend_yield - market.volatility**2 / 2) * tau
    )
    threshold = (log(option.strike) - mean) / width
    eta = 1 if option.option_type == OptionType.CALL else -1

    def integrand(z: float) -> float:
        # Truncation at 12 standard deviations avoids exponential overflow.
        terminal = exp(mean + width * z)
        return max(eta * (terminal - option.strike), 0) * exp(-z * z / 2)

    bounds = sorted({-12.0, 12.0, max(-12.0, min(12.0, threshold))})
    integral = sum(
        quad(integrand, left, right, epsabs=1e-11, epsrel=1e-11)[0]
        for left, right in zip(bounds, bounds[1:])
    )
    return exp(-market.rate * tau) * integral / sqrt(2 * pi)


def finite_difference_greeks(
    option: EuropeanOption, market: MarketSnapshot, relative_step: float = 1e-4
) -> GreeksResult:
    """Central differences holding other inputs fixed.

    Volatility/rate use max(abs(value), .01) as their step scale.
    Theta uses the negative remaining-tenor derivative for calendar-time decay.
    """
    if not 0 < relative_step < 0.1:
        raise ValueError("relative_step must be between zero and .1")
    tau = option.maturity - market.time
    if tau <= 0 or market.volatility <= 0:
        raise ValueError("finite differences require positive tenor and volatility")

    def derivative(field: str, scale: float) -> float:
        step = relative_step * scale
        plus = price(option, replace(market, **{field: getattr(market, field) + step}))
        minus = price(option, replace(market, **{field: getattr(market, field) - step}))
        return (plus - minus) / (2 * step)

    step = market.spot * relative_step
    up = price(option, replace(market, spot=market.spot + step))
    down = price(option, replace(market, spot=market.spot - step))
    # Bump remaining tenor for theta, including observations at time zero.
    tenor_step = tau * relative_step
    theta = (
        price(replace(option, maturity=option.maturity - tenor_step), market)
        - price(replace(option, maturity=option.maturity + tenor_step), market)
    ) / (2 * tenor_step)
    return GreeksResult(
        derivative("spot", market.spot),
        (up - 2 * price(option, market) + down) / step**2,
        derivative("volatility", market.volatility),
        theta,
        derivative("rate", max(abs(market.rate), 0.01)),
    )
