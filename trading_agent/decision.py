"""Decision models. The agent only needs an object with decide(snapshot) -> Decision."""

from typing import Protocol

from .schema import Decision


class DecisionModel(Protocol):
    def decide(self, snap: dict) -> Decision: ...


class StubDecisionModel:
    """Placeholder rule set so the pipeline runs end to end.

    It has no demonstrated edge. Do not trust its output as a strategy. Replace
    it with a real model adapter, which must return validated Decision objects.
    """

    def decide(self, snap):
        imb = snap["imb"]
        strength = min(abs(imb), 1.0)
        if imb > 0.3:
            direction = "long"
        elif imb < -0.3:
            direction = "short"
        else:
            direction = "neutral"
        if snap["rvol"] > 0.01:
            regime = "crisis"
        elif snap["rvol"] > 0.002:
            regime = "high_vol"
        else:
            regime = "mean_reverting"
        return Decision(
            regime=regime,
            direction=direction,
            toxic_flow=snap["spr"] > 30,
            setup_quality=3 if strength > 0.5 else 2 if strength > 0.3 else 0,
            risk_state="near_limit" if snap["spr"] > 50 else "safe",
            confidence=0.5 + 0.5 * strength,
            p_win=0.5 + 0.2 * strength,
            payoff=1.0,
        )
