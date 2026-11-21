"""European contract definitions, independent of market observations."""

from dataclasses import dataclass
from enum import Enum

from ._validation import finite_real


class OptionType(str, Enum):
    """Direction of the terminal payoff."""

    CALL = "call"
    PUT = "put"


@dataclass(frozen=True)
class EuropeanOption:
    """Long option specification; maturity is an absolute model time in years.

    Prices and Greeks are per share. Multiplier scales contract values only
    when explicitly applied by the caller.
    """

    option_type: OptionType
    strike: float
    maturity: float
    multiplier: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.option_type, OptionType):
            raise TypeError("option_type must be OptionType")
        for name in ("strike", "maturity", "multiplier"):
            finite_real(name, getattr(self, name))
        if self.strike <= 0 or self.multiplier <= 0 or self.maturity < 0:
            raise ValueError("strike/multiplier must be positive; maturity nonnegative")
