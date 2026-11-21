# Options Pricing, Risk & Hedging Analytics Platform

A reproducible European equity option research project. Phase 1 provides scalar
Black-Scholes-Merton call/put prices, analytical Delta, Gamma, Vega, Theta and Rho,
and independent deterministic numerical validation.

## Installation

Python 3.11+ is required.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest -v
python examples/analytical_pricing.py
```

The package uses NumPy and SciPy. The development extra adds pytest and Ruff.

## Quick start

```python
from optionlab import EuropeanOption, MarketSnapshot, OptionType, greeks, price

option = EuropeanOption(OptionType.CALL, strike=100, maturity=1, multiplier=100)
market = MarketSnapshot(spot=100, rate=0.03, dividend_yield=0.01, volatility=0.20)
print(price(option, market))  # approximately 8.8273212254 per share
print(greeks(option, market))
```

The example prints both option types, contract values, all Greeks with units,
put-call parity residual and computed integration/finite-difference errors.

## Mathematical conventions

- Frozen models use a shared year clock. Remaining tenor is option maturity minus
  market time, with 252 trading steps per year for future simulation.
- Spot and strike are positive, tenor and volatility nonnegative, and all inputs
  finite real scalars. Negative continuously compounded rates and dividend yields
  are supported. Use OptionType.CALL or OptionType.PUT.
- Values and sensitivities describe one long option per share. Multiply by the
  positive contract multiplier and signed contract count for position exposure.
  An empty short-call portfolio would buy positive delta shares to offset its
  negative option delta.
- Delta is shares per option share, Gamma is inverse currency, Vega is currency
  per share per unit absolute volatility, Rho per unit rate, and Theta per calendar
  year. Scale Vega by .01 for one volatility point, Rho by .0001 for one basis
  point, and Theta by 1/252 for one trading day.
- At expiry, price is intrinsic payoff. At zero volatility it is discounted
  deterministic payoff. Boundary Greeks have None fields and an explicit
  expiry or zero_volatility status, as specified by the design.
- Pricing uses logarithmic tail probabilities, expm1 differences and put-call
  parity. The core implements the formulas directly using SciPy probability
  primitives.

The full formulas and accounting design are in
[the architecture](docs/SYSTEM_ARCHITECTURE.md).

## Validation methodology

Tests compare prices with direct discounted GBM payoff quadrature split at the
strike, check parity, bounds, monotonicity, negative rates, deterministic limits,
small maturities, tails and invalid inputs. All five Greeks are checked with
central differences at three relative bump sizes. Tests use the absolute-plus-
relative tolerance specified in [the validation plan](docs/VALIDATION_PLAN.md).

The validation module is independent of the analytical formula for integration,
and uses the public price function for differences. Quadrature truncates the
standard normal domain at ±12 and targets moderate parameters. It serves as a
numerical reference for the documented test grid.

## Implemented scope and limitations

The public API accepts scalar inputs. Extremely large discounted values or
sensitivities outside floating-point range raise ValueError; tiny tail values
can underflow. Boundary sensitivities use a conservative missing-value policy.
The model assumes constant rates, yield and volatility, continuous frictionless
pricing, and European exercise. Monte Carlo, dynamic hedging and risk research
are scheduled in [the roadmap](docs/MASTER_PLAN.md).

Actual validation records are tracked in
[the evidence ledger](docs/RESUME_EVIDENCE.md). No performance benchmark has been
established.
