"""Local Greek explain and full revaluation of a short call with stock."""

from dataclasses import asdict, replace
from math import isclose

from . import EuropeanOption, MarketSnapshot, OptionType, greeks, price


def _terms(option, market, shares, ds, dt, dv):
    g = greeks(option, market)
    if option.option_type != OptionType.CALL or g.status != "regular":
        raise ValueError("requires a live short call with positive implied volatility")
    m = option.multiplier
    return dict(
        delta=(shares - m * g.delta) * ds,
        gamma=-0.5 * m * g.gamma * ds**2,
        theta=-m * g.theta * dt,
        vega=-m * g.vega * dv,
    )


def revalue(
    option: EuropeanOption,
    market: MarketSnapshot,
    shares: float,
    cash: float,
    spot_shift: float,
    vol_shift: float,
) -> dict:
    """Instantaneous full repricing with frozen stock and cash (absolute shocks)."""
    shocked = replace(
        market, spot=market.spot + spot_shift, volatility=market.volatility + vol_shift
    )

    def snapshot(m):
        value = price(option, m)
        return dict(
            spot=m.spot,
            volatility=m.volatility,
            price=value,
            equity=cash + shares * m.spot - option.multiplier * value,
            greeks=asdict(greeks(option, m)),
        )

    before, after = snapshot(market), snapshot(shocked)
    actual = after["equity"] - before["equity"]
    terms = _terms(option, market, shares, spot_shift, 0, vol_shift)
    return dict(
        before=before,
        after=after,
        actual=actual,
        terms=terms,
        residual=actual - sum(terms.values()),
    )


def attribute(
    option: EuropeanOption, market: MarketSnapshot, ledger: list[dict]
) -> list[dict]:
    """Explain a complete Phase 3 ledger. Optional row IV is the mark's IV."""
    if (
        not ledger
        or ledger[0]["step"] != 0
        or "cash_after_settlement" not in ledger[-1]
    ):
        raise ValueError("complete ledger required")
    output = []
    for i, row in enumerate(ledger):
        if row["step"] != i or row["path_id"] != ledger[0]["path_id"]:
            raise ValueError("ledger path or event order mismatch")
        prev = ledger[i - 1] if i else row
        dt = row["time"] - prev["time"]
        if i and dt <= 0:
            raise ValueError("ledger times must increase")
        left = replace(
            market,
            time=prev["time"],
            spot=prev["spot"],
            volatility=prev.get("volatility", market.volatility),
        )
        ds = row["spot"] - prev["spot"]
        terms = _terms(
            option,
            left,
            prev["shares_after"],
            ds,
            dt,
            row.get("volatility", market.volatility) - left.volatility,
        )
        terms.update(
            financing=row["interest"],
            dividend=row["dividend"],
            fees=-row["fee"],
            other=row.get("other_cash_flow", 0.0),
        )
        actual = row["equity"] - (prev["equity"] if i else 0)
        exact = (
            prev["shares_after"] * ds - (row["liability"] - prev["liability"])
            if i
            else row["premium"] - row["liability"]
        )
        exact += terms["financing"] + terms["dividend"] + terms["fees"] + terms["other"]
        if not isclose(actual, exact, abs_tol=1e-9, rel_tol=1e-10):
            raise ValueError("ledger equity reconciliation failed")
        output.append(
            dict(
                step=i,
                actual=actual,
                terms=terms,
                exact_error=actual - exact,
                residual=actual - sum(terms.values()),
            )
        )
    final = ledger[-1]
    payoff = option.multiplier * max(final["spot"] - option.strike, 0)
    if not (
        final["shares_after"] == 0
        and isclose(final["settlement"], payoff)
        and isclose(final["liability"], payoff)
        and isclose(final["cash_after_settlement"], final["equity"], abs_tol=1e-9)
    ):
        raise ValueError("terminal settlement mismatch")
    return output
