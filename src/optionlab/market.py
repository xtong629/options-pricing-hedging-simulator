"""Immutable scalar market observations."""

from dataclasses import dataclass

from ._validation import finite_real


@dataclass(frozen=True)
class MarketSnapshot:
    """Ex-dividend spot and continuously compounded annual rates.

    Volatility is annualized in absolute units, e.g. 0.20 for 20%.
    Time uses the same year clock as the contract maturity.
    """

    spot: float
    rate: float
    dividend_yield: float
    volatility: float
    time: float = 0.0

    def __post_init__(self) -> None:
        for name in ("spot", "rate", "dividend_yield", "volatility", "time"):
            finite_real(name, getattr(self, name))
        if self.spot <= 0 or self.volatility < 0 or self.time < 0:
            raise ValueError("spot must be positive; volatility/time nonnegative")
