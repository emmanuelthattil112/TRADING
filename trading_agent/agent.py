"""Tick loop: book -> state -> model -> risk -> paper order, filled on the next book.

The order decided on book t is filled on book t+1, so a decision never trades
on the same book it was made from.
"""

from dataclasses import asdict

from .execution import Order
from .schema import DecisionError


class TradingAgent:
    def __init__(self, engine, model, risk, broker, escalator=None, journal=None):
        self.engine = engine
        self.model = model
        self.risk = risk
        self.broker = broker
        self.escalator = escalator
        self.journal = journal
        self._pending = None
        self._open = None  # (p_win, equity after entry fee) for the open trade

    def step(self, book):
        self.engine.on_book(book)
        fill = None
        if self._pending is not None:
            fill = self._settle(self._pending, book)
            self._pending = None

        snap = self.engine.snapshot()
        d, verdict, source = self._decide(snap)
        order = self._order(verdict, d)
        if order is not None:
            self._pending = order

        record = {
            "type": "step",
            "t": snap["t"],
            "snap": snap,
            "source": source,
            "decision": asdict(d) if d is not None else None,
            "action": verdict.action,
            "reason": verdict.reason,
            "fill": fill,
        }
        if self.journal is not None:
            self.journal.write(record)
        return record

    def _decide(self, snap):
        try:
            d = self.model.decide(snap)
        except DecisionError:
            return None, self.risk.exit_or_hold(self.engine, "invalid_decision"), "invalid"

        verdict = self.risk.check(d, snap, self.engine)
        if verdict.action != "escalate":
            return d, verdict, "model"
        if self.escalator is None:
            return d, self.risk.exit_or_hold(self.engine, "escalation_unavailable"), "model"

        try:
            d2 = self.escalator.decide(snap)
        except DecisionError:
            return None, self.risk.exit_or_hold(self.engine, "invalid_escalation"), "escalated"
        verdict2 = self.risk.check(d2, snap, self.engine)
        if verdict2.action == "escalate":
            verdict2 = self.risk.exit_or_hold(self.engine, "escalation_unresolved")
        return d2, verdict2, "escalated"

    def _order(self, verdict, d):
        if verdict.action in ("enter_long", "enter_short"):
            side = 1 if verdict.action == "enter_long" else -1
            return Order(side * verdict.notional / self.engine.mid, verdict.reason, d.p_win)
        if verdict.action == "flatten" and self.engine.position != 0:
            return Order(-self.engine.position, verdict.reason, None)
        return None

    def _settle(self, order, book):
        before = self.engine.position
        fill = self.broker.execute(order, book, self.engine)
        if fill is None:
            return None
        if before == 0 and self.engine.position != 0:
            self._open = (order.p_win, self.engine.equity)
        elif before != 0 and self.engine.position == 0 and self._open is not None:
            p_win, entry_equity = self._open
            self._open = None
            if self.journal is not None:
                self.journal.write(
                    {"type": "outcome", "p_win": p_win, "won": self.engine.equity > entry_equity}
                )
        return fill
