"""Compare Q estimates after installing the package."""

from optionlab import (
    EuropeanOption,
    MarketSnapshot,
    MonteCarloConfig,
    OptionType,
    mc_price,
    price,
)

market = MarketSnapshot(100, 0.03, 0.01, 0.2)
print("CU/share, long option; S=K=100, tenor=1 year, r=.03, q=.01, sigma=.20")
for kind in OptionType:
    option = EuropeanOption(kind, 100, 1)
    analytical = price(option, market)
    print(f"\n{kind.value}: analytical={analytical:.8f}")
    for method in ("standard", "antithetic"):
        result = mc_price(option, market, MonteCarloConfig(100_000, method, 20261122))
        print(
            f"{method}: price={result.estimate:.8f}, SE={result.standard_error:.8f}, "
            f"95% CI={result.confidence_interval}, "
            f"absolute error={abs(result.estimate - analytical):.8f}, "
            f"paths={result.n_paths}, "
            f"independent observations={result.n_observations}, "
            f"seed={result.seed}, RNG={result.bit_generator}"
        )
