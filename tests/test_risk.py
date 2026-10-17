from pathlib import Path

import pytest

from trading_agent.config import RiskLimits
from trading_agent.risk import RiskLayer
from trading_agent.schema import Decision
from trading_agent.state import Book, StateEngine


def make_engine(tmp_path, position=0.0):
    eng = StateEngine(10_000, fee_bps=0)
    eng.on_book(Book(ts=1.0, bids=((100.0, 5.0),), asks=((101.0, 5.0),)))
    if position:
        eng.apply_fill(position, 101.0)
    return eng


def make_decision(**overrides):
    base = dict(
        regime="trending",
        direction="long",
        toxic_flow=False,
        setup_quality=3,
        risk_state="safe",
        confidence=0.9,
        p_win=0.6,
        payoff=1.0,
    )
    return Decision(**{**base, **overrides})


def snap(eng, **overrides):
    return {**eng.snapshot(), **overrides}


def layer(tmp_path, **limits):
    limits.setdefault("kill_switch_file", tmp_path / "KILL")
    return RiskLayer(RiskLimits(**limits))


def test_clean_setup_enters_long(tmp_path):
    eng = make_engine(tmp_path)
    v = layer(tmp_path).check(make_decision(), snap(eng), eng)
    assert v.action == "enter_long"
    assert 0 < v.notional <= 1_000


def test_short_direction_enters_short(tmp_path):
    eng = make_engine(tmp_path)
    v = layer(tmp_path).check(make_decision(direction="short"), snap(eng), eng)
    assert v.action == "enter_short"


def test_kill_switch_file_flattens_open_position(tmp_path):
    eng = make_engine(tmp_path, position=2.0)
    (tmp_path / "KILL").write_text("stop")
    v = layer(tmp_path).check(make_decision(), snap(eng), eng)
    assert v.action == "flatten" and v.reason == "kill_switch"


def test_kill_switch_blocks_entries(tmp_path):
    eng = make_engine(tmp_path)
    (tmp_path / "KILL").write_text("stop")
    v = layer(tmp_path).check(make_decision(), snap(eng), eng)
    assert v.action == "hold" and v.reason == "kill_switch"


def test_drawdown_limit_flattens(tmp_path):
    eng = make_engine(tmp_path, position=2.0)
    v = layer(tmp_path).check(make_decision(), snap(eng, dd=0.15), eng)
    assert v.action == "flatten" and v.reason == "max_drawdown"


def test_daily_loss_limit_flattens_or_holds(tmp_path):
    eng = make_engine(tmp_path)
    v = layer(tmp_path).check(make_decision(), snap(eng, dloss=100.0), eng)
    assert v.action == "hold" and v.reason == "max_daily_loss"


def test_crisis_escalates(tmp_path):
    eng = make_engine(tmp_path)
    v = layer(tmp_path).check(make_decision(regime="crisis"), snap(eng), eng)
    assert v.action == "escalate"


def test_low_confidence_escalates_but_mid_confidence_holds(tmp_path):
    eng = make_engine(tmp_path)
    risk = layer(tmp_path)
    assert risk.check(make_decision(confidence=0.5), snap(eng), eng).action == "escalate"
    assert risk.check(make_decision(confidence=0.7), snap(eng), eng).action == "hold"


@pytest.mark.parametrize(
    "overrides,reason",
    [
        (dict(setup_quality=1), "setup_quality"),
        (dict(confidence=0.79), "confidence"),
        (dict(toxic_flow=True), "toxic_flow"),
        (dict(risk_state="near_limit"), "risk_state_not_safe"),
        (dict(direction="neutral"), "neutral"),
    ],
)
def test_entry_gates_hold(tmp_path, overrides, reason):
    eng = make_engine(tmp_path)
    v = layer(tmp_path).check(make_decision(**overrides), snap(eng), eng)
    assert v.action == "hold" and v.reason == reason


def test_reduce_flattens_position(tmp_path):
    eng = make_engine(tmp_path, position=2.0)
    v = layer(tmp_path).check(make_decision(risk_state="reduce"), snap(eng), eng)
    assert v.action == "flatten"


def test_opposing_signal_flattens(tmp_path):
    eng = make_engine(tmp_path, position=2.0)
    v = layer(tmp_path).check(make_decision(direction="short"), snap(eng), eng)
    assert v.action == "flatten" and v.reason == "opposing_signal"


def test_same_direction_does_not_pyramid(tmp_path):
    eng = make_engine(tmp_path, position=2.0)
    v = layer(tmp_path).check(make_decision(direction="long"), snap(eng), eng)
    assert v.action == "hold" and v.reason == "already_positioned"
