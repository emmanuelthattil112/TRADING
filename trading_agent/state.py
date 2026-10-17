"""Deterministic state engine: order book in, one compact numeric snapshot out.

Every feature is computed here, in code. The model sees only the snapshot.
Events must arrive in time order, and a snapshot uses only events up to and
including its own timestamp, so no field can read from the future.
"""

import math
from collections import deque
from dataclasses import dataclass
from statistics import pstdev


@dataclass(frozen=True)
class Book:
    ts: float
    bids: tuple  # ((price, size), ...) best bid first
    asks: tuple  # ((price, size), ...) best ask first

    @classmethod
    def from_json(cls, row):
        return cls(
            ts=float(row["ts"]),
            bids=tuple((float(p), float(s)) for p, s in row["bids"]),
            asks=tuple((float(p), float(s)) for p, s in row["asks"]),
        )


class StateEngine:
    def __init__(self, equity, depth=5, window=50, fee_bps=10.0):
        self.depth = depth
        self.fee_bps = fee_bps
        self.cash = equity
        self.position = 0.0  # base units, negative means short
        self.mid = None
        self.equity = equity
        self.peak = equity
        self.day_start_equity = equity
        self._mids = deque(maxlen=window)
        self._last_ts = None
        self._t = None
        self._spr = 0.0
        self._imb = 0.0
        self._rvol = 0.0

    def on_book(self, book):
        self._check(book)
        self._last_ts = book.ts
        best_bid, best_ask = book.bids[0][0], book.asks[0][0]
        self.mid = (best_bid + best_ask) / 2
        self._mids.append(self.mid)
        bid_sz = sum(s for _, s in book.bids[: self.depth])
        ask_sz = sum(s for _, s in book.asks[: self.depth])
        self._t = book.ts
        self._spr = (best_ask - best_bid) / self.mid * 1e4
        self._imb = (bid_sz - ask_sz) / (bid_sz + ask_sz)
        self._rvol = self._realized_vol()
        self._mark()

    def snapshot(self):
        return {
            "t": self._t,
            "mid": self.mid,
            "spr": self._spr,
            "imb": self._imb,
            "rvol": self._rvol,
            "inv": self.position * self.mid,
            "eq": self.equity,
            "dd": self.drawdown,
            "dloss": self.day_start_equity - self.equity,
        }

    @property
    def drawdown(self):
        return max(0.0, 1 - self.equity / self.peak)

    def apply_fill(self, qty, price):
        notional = qty * price
        fee = abs(notional) * self.fee_bps / 1e4
        self.cash -= notional + fee
        self.position += qty
        if abs(self.position) < 1e-12:
            self.position = 0.0
        self._mark()
        return fee

    def new_day(self):
        self.day_start_equity = self.equity

    def _mark(self):
        self.equity = self.cash + self.position * self.mid
        self.peak = max(self.peak, self.equity)

    def _realized_vol(self):
        mids = list(self._mids)
        if len(mids) < 3:
            return 0.0
        rets = [math.log(b / a) for a, b in zip(mids, mids[1:])]
        return pstdev(rets)

    def _check(self, book):
        if not book.bids or not book.asks:
            raise ValueError("book has an empty side")
        if self._last_ts is not None and book.ts < self._last_ts:
            raise ValueError("out-of-order event")
        if any(s <= 0 for _, s in book.bids + book.asks):
            raise ValueError("non-positive size")
        bids = [p for p, _ in book.bids]
        asks = [p for p, _ in book.asks]
        if any(x <= y for x, y in zip(bids, bids[1:])):
            raise ValueError("bids not strictly descending")
        if any(x >= y for x, y in zip(asks, asks[1:])):
            raise ValueError("asks not strictly ascending")
        if bids[0] >= asks[0]:
            raise ValueError("crossed book")


def render(snap):
    """One line of key=value text. This is what a model would receive."""
    return " ".join(f"{k}={v:.6g}" for k, v in snap.items())
