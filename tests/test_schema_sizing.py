import pytest

from trading_agent.config import RiskLimits
from trading_agent.schema import Decision, DecisionError
from trading_agent.sizing import kelly_fraction, position_notional

VALID = dict(
    regime="trending",
    direction="long",
    toxic_flow=False,
    setup_quality=3,
    risk_state="safe",
    confidence=0.9,
    p_win=0.6,
    payoff=1.0,
)


def test_valid_decision_builds():
    assert Decision(**VALID).direction == "long"


@pytest.mark.parametrize(
    "field,value",
    [
        ("regime", "sideways"),
        ("direction", "up"),
        ("risk_state", "ok"),
        ("toxic_flow", "no"),
        ("setup_quality", 4),
        ("setup_quality", True),
        ("confidence", 1.2),
        ("confidence", float("nan")),
        ("p_win", -0.1),
        ("payoff", 0),
        ("payoff", float("inf")),
    ],
)
def test_invalid_fields_rejected(field, value):
    with pytest.raises(DecisionError):
        Decision(**{**VALID, field: value})


def test_unknown_or_missing_keys_rejected():
    with pytest.raises(DecisionError):
        Decision.from_dict({**VALID, "extra": 1})
    with pytest.raises(DecisionError):
        Decision.from_dict({k: v for k, v in VALID.items() if k != "payoff"})


def test_kelly_zero_without_edge():
    assert kelly_fraction(0.5, 1.0) == 0.0
    assert kelly_fraction(0.4, 1.0) == 0.0


def test_kelly_value():
    assert kelly_fraction(0.6, 1.0) == pytest.approx(0.2)


def test_quarter_kelly_then_caps():
    limits = RiskLimits()
    # Quarter Kelly of 0.2 is 0.05 of equity, under the 10% per-trade cap.
    assert position_notional(10_000, 0.6, 1.0, limits) == pytest.approx(500)
    # Huge edge still respects the per-trade equity cap and the notional cap.
    assert position_notional(10_000, 0.99, 1.0, limits) == pytest.approx(1_000)
    assert position_notional(1_000_000, 0.99, 1.0, limits) == pytest.approx(1_000)
    assert position_notional(10_000, 0.4, 1.0, limits) == 0.0
