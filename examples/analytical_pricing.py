"""Run with python examples/analytical_pricing.py after installing the package."""

from math import exp

from optionlab import EuropeanOption, MarketSnapshot, OptionType, greeks, price
from optionlab.validation import finite_difference_greeks, integrated_price

market = MarketSnapshot(spot=100, rate=0.03, dividend_yield=0.01, volatility=0.2)
print("Fictional European equity option; currency units (CU)")
print("S=100 CU, K=100 CU, T=1 year, r=3%, q=1%, sigma=20%, multiplier=100")
prices = {}
for kind in OptionType:
    option = EuropeanOption(kind, strike=100, maturity=1, multiplier=100)
    value = price(option, market)
    prices[kind] = value
    print(f"\n{kind.value}: {value:.10f} CU/share; {value * 100:.8f} CU/contract")
    result = greeks(option, market)
    numeric = finite_difference_greeks(option, market)
    for field, unit in (
        ("delta", "shares/share"),
        ("gamma", "per CU"),
        ("vega", "CU/share per unit volatility"),
        ("theta", "CU/share per calendar year"),
        ("rho", "CU/share per unit rate"),
    ):
        print(f"{field}: {getattr(result, field):.10f} {unit}")
    integration_error = abs(value - integrated_price(option, market))
    print(f"Integration absolute error: {integration_error:.3e}")
    errors = [
        abs(getattr(result, f) - getattr(numeric, f))
        for f in ("delta", "gamma", "vega", "theta", "rho")
    ]
    print("Central-difference absolute errors (Delta, Gamma, Vega, Theta, Rho):")
    print(" ".join(f"{error:.3e}" for error in errors))
residual = (
    prices[OptionType.CALL]
    - prices[OptionType.PUT]
    - (100 * exp(-0.01) - 100 * exp(-0.03))
)
print(f"\nPut-call parity residual: {residual:.3e} CU/share")
