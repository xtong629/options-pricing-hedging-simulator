"""Risk-neutral terminal sampling and batched European Monte Carlo valuation."""

import json
from dataclasses import dataclass
from math import isfinite, sqrt
from numbers import Integral
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from ._validation import finite_real
from .instruments import EuropeanOption, OptionType
from .market import MarketSnapshot
from .pricing import price


@dataclass(frozen=True)
class MonteCarloConfig:
    """Path budget and independent-observation batch size.

    Standard uses one path per observation; antithetic uses two.
    Set seed=None when supplying a Generator, otherwise a local PCG64 is used.
    At least two independent observations are required to estimate variance.
    """

    n_paths: int = 100_000
    method: Literal["standard", "antithetic"] = "standard"
    seed: int | None = 0
    batch_size: int = 4096

    def __post_init__(self) -> None:
        for name in ("n_paths", "batch_size"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.method not in ("standard", "antithetic"):
            raise ValueError("method must be standard or antithetic")
        if self.seed is not None:
            if isinstance(self.seed, bool) or not isinstance(self.seed, Integral):
                raise TypeError("seed must be an integer or None")
            if self.seed < 0:
                raise ValueError("seed must be nonnegative")
        if self.method == "antithetic" and self.n_paths % 2:
            raise ValueError("antithetic requires an even path count")
        if self.n_observations < 2:
            raise ValueError("at least two independent observations are required")

    @property
    def n_observations(self) -> int:
        """Number of independent payoffs or antithetic pair averages."""
        return self.n_paths // 2 if self.method == "antithetic" else self.n_paths


@dataclass(frozen=True)
class MonteCarloResult:
    """Long per-share currency statistics of independent discounted observations.

    sample_std is the standard deviation of ordinary payoffs or pair means.
    rng_state is the serialized initial bit-generator state, captured before use.
    The approximate normal 95% interval uses estimate ±1.96*standard_error.
    """

    estimate: float
    sample_std: float
    standard_error: float
    confidence_interval: tuple[float, float]
    n_paths: int
    n_observations: int
    method: str
    seed: int | None
    bit_generator: str
    rng_state: str


def gbm_terminal(
    market: MarketSnapshot, time_to_maturity: float, normals: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Map finite standard-normal draws to ex-dividend Q terminal spots.

    Drift is r-q. This function has no RNG side effects and returns one
    float64 array shaped like the input, without retaining intermediate paths.
    """
    finite_real("time_to_maturity", time_to_maturity)
    if time_to_maturity < 0:
        raise ValueError("time_to_maturity must be nonnegative")
    z = np.asarray(normals, dtype=np.float64)
    if not np.all(np.isfinite(z)):
        raise ValueError("normals must be finite")
    tau = time_to_maturity
    with np.errstate(over="raise", invalid="raise"):
        try:
            log_terminal = (
                np.log(market.spot)
                + (market.rate - market.dividend_yield - market.volatility**2 / 2) * tau
                + market.volatility * sqrt(tau) * z
            )
            return np.exp(log_terminal)
        except (FloatingPointError, OverflowError) as error:
            raise ValueError(
                "GBM terminal values exceed floating-point range"
            ) from error


def mc_price(
    option: EuropeanOption,
    market: MarketSnapshot,
    config: MonteCarloConfig = MonteCarloConfig(),
    rng: np.random.Generator | None = None,
) -> MonteCarloResult:
    """Estimate discounted payoff under Q using stable merged batch moments.

    A supplied Generator is advanced in place. Batch size changes only rounding
    of the reductions for a fixed Generator stream. Deterministic boundaries
    return exact analytical boundary value, zero uncertainty and consume no RNG.
    """
    tau = option.maturity - market.time
    if tau < 0:
        raise ValueError("market time must not exceed maturity")
    if rng is not None and not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a NumPy Generator")
    if rng is not None and config.seed is not None:
        raise ValueError("set config.seed=None when supplying rng")
    generator = (
        rng if rng is not None else np.random.Generator(np.random.PCG64(config.seed))
    )
    initial_state = json.dumps(
        generator.bit_generator.state,
        default=lambda x: x.tolist() if isinstance(x, np.ndarray) else int(x),
        sort_keys=True,
    )
    bit_generator = type(generator.bit_generator).__name__

    def result(mean: float, sample_std: float) -> MonteCarloResult:
        se = sample_std / sqrt(config.n_observations)
        interval = (mean - 1.96 * se, mean + 1.96 * se)
        if not all(isfinite(x) for x in interval):
            raise ValueError("confidence interval exceeds floating-point range")
        return MonteCarloResult(
            mean,
            sample_std,
            se,
            interval,
            config.n_paths,
            config.n_observations,
            config.method,
            config.seed,
            bit_generator,
            initial_state,
        )

    if tau == 0 or market.volatility == 0:
        return result(price(option, market), 0.0)
    eta = 1 if option.option_type == OptionType.CALL else -1
    with np.errstate(over="raise", invalid="raise"):
        try:
            discount = np.exp(-market.rate * tau)

            def payoff(z: NDArray[np.float64]) -> NDArray[np.float64]:
                terminal = gbm_terminal(market, tau, z)
                return discount * np.maximum(eta * (terminal - option.strike), 0)

            count, mean, m2 = 0, 0.0, 0.0
            while count < config.n_observations:
                size = min(config.batch_size, config.n_observations - count)
                z = generator.standard_normal(size)
                observations = payoff(z)
                if config.method == "antithetic":
                    observations = observations / 2 + payoff(-z) / 2
                batch_mean = float(np.mean(observations))
                batch_m2 = float(np.sum((observations - batch_mean) ** 2))
                total = count + size
                delta = batch_mean - mean
                m2 += batch_m2 + delta**2 * count * size / total
                mean += delta * size / total
                count = total
            std = sqrt(m2 / (count - 1))
        except (FloatingPointError, OverflowError) as error:
            raise ValueError(
                "Monte Carlo moments exceed floating-point range"
            ) from error
    if not all(isfinite(x) for x in (mean, std)):
        raise ValueError("Monte Carlo moments exceed floating-point range")
    return result(mean, std)
