"""Cash and stock accounting for a single short European call."""

from dataclasses import dataclass
from math import exp, isfinite


@dataclass
class PortfolioState:
    """Mutable state in currency units and shares."""

    cash: float = 0.0
    shares: float = 0.0

    def equity(self, spot: float, liability: float) -> float:
        """Mark the short option liability and stock at the current spot."""
        return self.cash + self.shares * spot - liability

    def trade(self, target: float, spot: float, fee_rate: float) -> tuple[float, float]:
        """Trade to target and return signed shares traded and currency fee."""
        if not all(isfinite(x) for x in (target, spot, fee_rate)):
            raise ValueError("trade inputs must be finite")
        if spot <= 0 or fee_rate < 0:
            raise ValueError("spot must be positive and fee rate nonnegative")
        quantity = target - self.shares
        cost = fee_rate * abs(quantity) * spot
        self.cash -= quantity * spot + cost
        self.shares = target
        return quantity, cost

    def accrue(
        self, spot: float, rate: float, dividend_yield: float, dt: float
    ) -> tuple[float, float]:
        """Accrue cash at r and credit left-point stock dividend at interval end."""
        if not all(isfinite(x) for x in (spot, rate, dividend_yield, dt)):
            raise ValueError("accrual inputs must be finite")
        if spot <= 0 or dt < 0:
            raise ValueError("spot must be positive and dt nonnegative")
        interest = self.cash * (exp(rate * dt) - 1)
        dividend = self.shares * dividend_yield * spot * dt
        self.cash += interest + dividend
        return interest, dividend
