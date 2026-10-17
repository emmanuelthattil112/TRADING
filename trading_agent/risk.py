"""Deterministic risk layer. The decision model cannot override anything here."""

from dataclasses import dataclass

from .sizing import position_notional

SIDE = {"long": 1, "short": -1, "neutral": 0}


@dataclass(frozen=True)
class Verdict:
    action: str  # enter_long, enter_short, flatten, hold, escalate
    reason: str
    notional: float = 0.0


class RiskLayer:
    def __init__(self, limits):
        self.limits = limits

    def kill_switch_armed(self):
        return self.limits.kill_switch_file.exists()

    def exit_or_hold(self, engine, reason):
        return Verdict("flatten" if engine.position != 0 else "hold", reason)

    def check(self, d, snap, engine):
        L = self.limits
        if self.kill_switch_armed():
            return self.exit_or_hold(engine, "kill_switch")
        if snap["dd"] >= L.max_drawdown:
            return self.exit_or_hold(engine, "max_drawdown")
        if snap["dloss"] >= L.max_daily_loss:
            return self.exit_or_hold(engine, "max_daily_loss")
        if d.regime == "crisis" or d.confidence < L.escalate_confidence:
            return Verdict("escalate", "crisis_or_low_confidence")
        if d.risk_state == "reduce":
            return self.exit_or_hold(engine, "model_reduce")

        side = SIDE[d.direction]
        position_side = (engine.position > 0) - (engine.position < 0)
        if position_side and side and side != position_side:
            return Verdict("flatten", "opposing_signal")

        if d.setup_quality < L.min_setup_quality:
            return Verdict("hold", "setup_quality")
        if d.confidence < L.min_confidence:
            return Verdict("hold", "confidence")
        if d.toxic_flow:
            return Verdict("hold", "toxic_flow")
        if d.risk_state != "safe":
            return Verdict("hold", "risk_state_not_safe")
        if side == 0:
            return Verdict("hold", "neutral")
        if position_side:
            return Verdict("hold", "already_positioned")

        notional = position_notional(engine.equity, d.p_win, d.payoff, L)
        if notional <= 0:
            return Verdict("hold", "zero_size")
        return Verdict("enter_long" if side > 0 else "enter_short", "entry", notional)
