"""Shared validation for scalar domain inputs."""

from math import isfinite
from numbers import Real


def finite_real(name: str, value: float) -> None:
    """Reject booleans, non-real values and non-finite inputs."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real scalar")
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
