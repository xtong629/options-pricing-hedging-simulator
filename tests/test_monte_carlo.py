"""Independent sample reconstruction and statistical acceptance tests."""

import json
from dataclasses import replace

import numpy as np
import pytest

from optionlab import (
    EuropeanOption,
    MarketSnapshot,
    MonteCarloConfig,
    OptionType,
    gbm_terminal,
    mc_price,
    price,
)

OPTION = EuropeanOption(OptionType.CALL, 100, 1, multiplier=100)
MARKET = MarketSnapshot(100, 0.03, 0.01, 0.2, time=0.1)


@pytest.mark.parametrize("method", ("standard", "antithetic"))
@pytest.mark.parametrize("kind", list(OptionType))
@pytest.mark.parametrize("rate,q", ((0.03, 0), (-0.02, 0.04)))
def test_bsm_comparison(method, kind, rate, q):
    option = replace(OPTION, option_type=kind)
    market = replace(MARKET, rate=rate, dividend_yield=q)
    result = mc_price(option, market, MonteCarloConfig(100_000, method, 104))
    assert (
        abs(result.estimate - price(option, market))
        <= 4 * result.standard_error + 1e-12
    )


@pytest.mark.parametrize("method", ("standard", "antithetic"))
@pytest.mark.parametrize("batch", (1, 7, 1000))
def test_reconstruct_observations_and_standard_error(method, batch):
    config = MonteCarloConfig(1000, method, 42, batch)
    z = np.random.Generator(np.random.PCG64(42)).standard_normal(config.n_observations)
    tau = OPTION.maturity - MARKET.time

    def independent_payoff(draws):
        terminal = MARKET.spot * np.exp(
            (MARKET.rate - MARKET.dividend_yield - 0.5 * MARKET.volatility**2) * tau
            + MARKET.volatility * np.sqrt(tau) * draws
        )
        return np.exp(-MARKET.rate * tau) * np.maximum(terminal - OPTION.strike, 0)

    observations = independent_payoff(z)
    if method == "antithetic":
        observations = (observations + independent_payoff(-z)) / 2
    result = mc_price(OPTION, MARKET, config)
    std = np.std(observations, ddof=1)
    se = std / np.sqrt(config.n_observations)
    assert result.n_paths == 1000
    assert result.n_observations == len(observations)
    assert result.estimate == pytest.approx(np.mean(observations), rel=1e-13)
    assert result.sample_std == pytest.approx(std, rel=1e-13)
    assert result.standard_error == pytest.approx(se, rel=1e-13)
    assert result.confidence_interval == pytest.approx(
        (result.estimate - 1.96 * se, result.estimate + 1.96 * se)
    )


@pytest.mark.parametrize("method", ("standard", "antithetic"))
def test_reproducibility_units_and_rng_state(method):
    config = MonteCarloConfig(1000, method, 12)
    first = mc_price(OPTION, MARKET, config)
    assert first == mc_price(OPTION, MARKET, config)
    assert first.estimate != mc_price(OPTION, MARKET, replace(config, seed=13)).estimate
    assert first == mc_price(replace(OPTION, multiplier=1), MARKET, config)
    assert first.bit_generator == "PCG64"
    bitgen = np.random.PCG64()
    bitgen.state = json.loads(first.rng_state)
    replay = mc_price(
        OPTION, MARKET, replace(config, seed=None), np.random.Generator(bitgen)
    )
    assert first.estimate == replay.estimate


@pytest.mark.parametrize("method", ("standard", "antithetic"))
@pytest.mark.parametrize("kind", list(OptionType))
@pytest.mark.parametrize("boundary", ("expiry", "zero_volatility"))
def test_deterministic_boundaries(method, kind, boundary):
    option = replace(OPTION, option_type=kind)
    market = replace(MARKET, spot=120)
    if boundary == "expiry":
        market = replace(market, time=option.maturity)
    else:
        market = replace(market, volatility=0)
    rng = np.random.default_rng(123)
    initial = json.dumps(rng.bit_generator.state)
    result = mc_price(option, market, MonteCarloConfig(100, method, None), rng)
    assert result.estimate == price(option, market)
    assert result.sample_std == result.standard_error == 0
    assert result.confidence_interval == (result.estimate, result.estimate)
    assert json.dumps(rng.bit_generator.state) == initial


@pytest.mark.parametrize("method", ("standard", "antithetic"))
def test_batch_invariance(method):
    base = MonteCarloConfig(1000, method, 123, 4096)
    reference = mc_price(OPTION, MARKET, base)
    for batch in (1, 13, 128):
        result = mc_price(OPTION, MARKET, replace(base, batch_size=batch))
        assert result.estimate == pytest.approx(reference.estimate, rel=1e-14)
        assert result.standard_error == pytest.approx(
            reference.standard_error, rel=1e-14
        )


@pytest.mark.parametrize(
    "field,bad,error",
    (
        ("n_paths", 0, ValueError),
        ("n_paths", -2, ValueError),
        ("n_paths", 1, ValueError),
        ("n_paths", 2.5, TypeError),
        ("n_paths", True, TypeError),
        ("n_paths", float("inf"), TypeError),
        ("batch_size", 0, ValueError),
        ("batch_size", 1.5, TypeError),
        ("batch_size", True, TypeError),
        ("method", "unknown", ValueError),
        ("seed", -1, ValueError),
        ("seed", 1.5, TypeError),
        ("seed", True, TypeError),
    ),
)
def test_invalid_config(field, bad, error):
    with pytest.raises(error):
        replace(MonteCarloConfig(), **{field: bad})


@pytest.mark.parametrize("count", (1, 2, 3, 5, 101))
def test_invalid_antithetic_counts(count):
    with pytest.raises(ValueError):
        MonteCarloConfig(count, "antithetic")


def test_invalid_clock_rng_and_overflow():
    with pytest.raises(ValueError):
        mc_price(OPTION, replace(MARKET, time=2))
    with pytest.raises(ValueError, match="seed"):
        mc_price(OPTION, MARKET, rng=np.random.default_rng(1))
    with pytest.raises(TypeError):
        mc_price(OPTION, MARKET, rng=123)
    with pytest.raises(ValueError, match="floating-point"):
        mc_price(OPTION, replace(MARKET, rate=-1000))
    with pytest.raises(ValueError):
        gbm_terminal(MARKET, -1, np.array([0.0]))
    with pytest.raises(ValueError):
        gbm_terminal(MARKET, 1, np.array([np.nan]))


def test_terminal_q_drift_and_moments():
    z = np.random.default_rng(1).standard_normal(100_000)
    terminal = gbm_terminal(MARKET, 0.9, z)
    increments = np.log(terminal / MARKET.spot)
    mean = (MARKET.rate - MARKET.dividend_yield - MARKET.volatility**2 / 2) * 0.9
    variance = MARKET.volatility**2 * 0.9
    assert abs(np.mean(increments) - mean) < 4 * np.sqrt(variance / len(z))
    assert np.var(increments) == pytest.approx(variance, rel=0.02)
    assert gbm_terminal(MARKET, 0, z) == pytest.approx(np.full(len(z), MARKET.spot))
