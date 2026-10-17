"""Paper execution only. There is intentionally no live exchange adapter yet."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    qty: float  # signed base units: positive buys, negative sells
    reason: str
    p_win: float | None


def _walk(levels, qty):
    """Fill qty against the book level by level. Returns (filled, vwap)."""
    remaining = qty
    cost = 0.0
    for price, size in levels:
        take = min(size, remaining)
        cost += take * price
        remaining -= take
        if remaining <= 1e-12:
            break
    filled = qty - remaining
    return filled, (cost / filled if filled > 0 else None)


class PaperBroker:
    """Taker fills against the current book. Partial fills when depth runs out.

    Not modelled: latency, queue position, market impact from our own size,
    and any change to the book between decision and fill beyond the next event.
    """

    def execute(self, order, book, engine):
        levels = book.asks if order.qty > 0 else book.bids
        sign = 1 if order.qty > 0 else -1
        filled, vwap = _walk(levels, abs(order.qty))
        if not filled:
            return None
        fee = engine.apply_fill(sign * filled, vwap)
        return {"t": book.ts, "qty": sign * filled, "price": vwap, "fee": fee, "reason": order.reason}
