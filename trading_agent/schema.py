"""Typed decision schema. Every model output must pass validation before use."""

import math
from dataclasses import dataclass

REGIMES = ("trending", "mean_reverting", "high_vol", "crisis")
DIRECTIONS = ("long", "short", "neutral")
RISK_STATES = ("safe", "near_limit", "reduce")


class DecisionError(ValueError):
    pass


def _one_of(name, value, allowed):
    if value not in allowed:
        raise DecisionError(f"{name} must be one of {allowed}, got {value!r}")


def _unit(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DecisionError(f"{name} must be a number")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise DecisionError(f"{name} must be in [0, 1], got {value!r}")


@dataclass(frozen=True)
class Decision:
    regime: str
    direction: str
    toxic_flow: bool
    setup_quality: int
    risk_state: str
    confidence: float
    p_win: float  # calibrated probability the trade wins
    payoff: float  # win-to-loss ratio, used for Kelly sizing

    def __post_init__(self):
        _one_of("regime", self.regime, REGIMES)
        _one_of("direction", self.direction, DIRECTIONS)
        _one_of("risk_state", self.risk_state, RISK_STATES)
        if not isinstance(self.toxic_flow, bool):
            raise DecisionError("toxic_flow must be a bool")
        if isinstance(self.setup_quality, bool) or not isinstance(self.setup_quality, int):
            raise DecisionError("setup_quality must be an int")
        if not 0 <= self.setup_quality <= 3:
            raise DecisionError("setup_quality must be in 0..3")
        _unit("confidence", self.confidence)
        _unit("p_win", self.p_win)
        if isinstance(self.payoff, bool) or not isinstance(self.payoff, (int, float)):
            raise DecisionError("payoff must be a number")
        if not math.isfinite(self.payoff) or self.payoff <= 0:
            raise DecisionError("payoff must be a positive finite number")

    @classmethod
    def from_dict(cls, raw):
        try:
            return cls(**raw)
        except TypeError as exc:
            raise DecisionError(str(exc)) from exc
