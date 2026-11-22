# Options Pricing, Risk & Hedging Analytics Platform

A reproducible European equity option research project. The analytical foundation provides scalar
Black-Scholes-Merton call/put prices, analytical Delta, Gamma, Vega, Theta and Rho,
and independent deterministic numerical validation. Phase 2 adds batched
risk-neutral Monte Carlo valuation and antithetic variance reduction.

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

Contract inputs are scalar; terminal sampling uses NumPy arrays. Extremely large discounted values or
sensitivities outside floating-point range raise ValueError; tiny tail values
can underflow. Boundary sensitivities use a conservative missing-value policy.
The model assumes constant rates, yield and volatility, continuous frictionless
pricing, and European exercise. Dynamic hedging and risk research
are scheduled in [the roadmap](docs/MASTER_PLAN.md).

Actual validation records are tracked in
[the evidence ledger](docs/RESUME_EVIDENCE.md). No performance benchmark has been
established.

## Monte Carlo valuation (Phase 2)

```python
from optionlab import MonteCarloConfig, mc_price

result = mc_price(
    option,
    market,
    MonteCarloConfig(
        n_paths=100_000, method="antithetic", seed=20261122, batch_size=4096
    ),
)
print(result)
```

Run the comparison example with
`python examples/monte_carlo_pricing.py`. Reproduce the multi-seed study with
`python -m optionlab.experiments --repeats 100 --full-grid --output /tmp/mc-study.json`.
The full study uses 100 independent seeds per method, option type and path budget,
plus a 24-configuration analytical comparison with both sampling methods.

Terminal GBM sampling uses Q drift r-q and discounts each payoff by exp(-rτ).
Standard sampling uses N independent payoffs. Antithetic sampling uses Z and -Z,
averages the two discounted payoffs, and estimates sample variance with ddof=1
over N/2 independent pair means. Both methods report sample standard deviation,
SE=s/sqrt(n), and the asymptotic 95% interval estimate ±1.96 SE.

At least two independent observations are required. Antithetic path counts must
be even. Batch size counts independent observations, with O(batch_size) working
memory. Merged centered moments avoid retaining paths; changing batch size can
change reduction rounding. Both methods use equal path budgets in the study,
although antithetic sampling needs half as many normal draws.

The default local Generator uses PCG64. A supplied NumPy Generator requires
config.seed=None, advances in place, and its initial serialized bit-generator
state is recorded in the result. Reproducibility requires the same NumPy version,
bit generator, state/seed and settings. Global random state is untouched.
Zero tenor/volatility returns the exact boundary price and zero uncertainty,
consumes no random draws, and retains the requested budget in result metadata.

Rare-payoff samples can contain only zeros, making an empirical interval
uninformative. Normal intervals have approximate repeated-sampling coverage and
can miss the analytical price. The study reports measured coverage with its
sampling SE and empirical log-RMSE slope across path budgets. Tiny values may
underflow, and nonrepresentable simulation values or moments raise ValueError.

Measured convergence and resource observations are in
[the Monte Carlo validation report](docs/MC_VALIDATION_REPORT.md).

## Discrete delta hedging (Phase 3)

`optionlab.hedging.physical_paths` generates physical-measure GBM paths.
`simulate_hedge` runs a short-call self-financing stock hedge with cash financing,
proportional trading costs, dividend accrual and settlement. Daily and weekly
strategies can consume the same input paths. An optional path-level ledger records
trades and cash flows. Run `python examples/hedging_research.py` to reproduce
the research and terminal arrays. See the
[hedging validation report](docs/HEDGING_VALIDATION_REPORT.md) for results,
model assumptions and limitations.
