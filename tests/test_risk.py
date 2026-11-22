import numpy as np
import pytest

from optionlab.risk import paired_bootstrap, summarize, tail_risk


@pytest.mark.parametrize(
    "losses,alpha,var,es",
    [
        ([-2, 0, 1, 5], 0.625, 1, 11 / 3),
        ([1, 1, 4, 4], 0.5, 1, 4),
        ([-3], 0.95, -3, -3),
        ([7] * 5, 0.95, 7, 7),
        ([-4, -2, 1, 3], 0.99, 3, 3),
        ([-4, -2, 1, 3], 0.25, -4, 2 / 3),
    ],
)
def test_hand_tail(losses, alpha, var, es):
    r = tail_risk(losses, alpha)
    assert r["var"] == var
    assert r["es"] == pytest.approx(es)


@pytest.mark.parametrize(
    "losses,alpha",
    [
        ([], 0.5),
        ([np.nan], 0.5),
        ([np.inf], 0.5),
        ([[1]], 0.5),
        ([1], 0),
        ([1], 1),
        ([1], np.nan),
        ([1], True),
    ],
)
def test_invalid(losses, alpha):
    with pytest.raises((ValueError, TypeError)):
        tail_risk(losses, alpha)


def test_pairing_and_sign():
    w = {i: v for i, v in enumerate([-12, 3, 4, 7, 9])}
    d = {i: w[i] + 2 for i in reversed(w)}
    r = paired_bootstrap(d, w, seed=3, replicates=50)
    for metric, shift in [("mean", 2), ("sd", 0), ("var", -2), ("es", -2)]:
        assert list(r[metric].values()) == pytest.approx([shift] * 3)
    assert r == paired_bootstrap(d, w, seed=3, replicates=50)
    assert r != paired_bootstrap(d, w, seed=5, replicates=50)
    with pytest.raises(ValueError):
        paired_bootstrap(d, {1: 2}, seed=1)
    assert summarize([1, -5])["worst_observed"] == 5
