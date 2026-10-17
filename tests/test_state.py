import pytest

from trading_agent.state import Book, StateEngine, render
from trading_agent.synthetic import generate


def book(ts, bid, ask, size=5.0, depth=3):
    return Book(
        ts=ts,
        bids=tuple((bid - i, size) for i in range(depth)),
        asks=tuple((ask + i, size) for i in range(depth)),
    )


def test_snapshot_uses_only_events_up_to_its_timestamp():
    eng = StateEngine(10_000)
    eng.on_book(book(1.0, 100, 101))
    snap = eng.snapshot()
    assert snap["t"] == 1.0
    assert snap["mid"] == 100.5


def test_out_of_order_event_rejected():
    eng = StateEngine(10_000)
    eng.on_book(book(2.0, 100, 101))
    with pytest.raises(ValueError, match="out-of-order"):
        eng.on_book(book(1.0, 100, 101))


def test_crossed_book_rejected():
    eng = StateEngine(10_000)
    with pytest.raises(ValueError, match="crossed"):
        eng.on_book(book(1.0, 101, 100))


def test_unsorted_levels_rejected():
    eng = StateEngine(10_000)
    bad = Book(ts=1.0, bids=((99, 1.0), (100, 1.0)), asks=((101, 1.0),))
    with pytest.raises(ValueError, match="descending"):
        eng.on_book(bad)


def test_snapshot_fits_token_budget():
    eng = StateEngine(10_000)
    for row in generate(300, seed=3):
        eng.on_book(Book.from_json(row))
    # Rough budget: about 4 characters per token, so 1600 characters is about 400 tokens.
    assert len(render(eng.snapshot())) < 1600


def test_drawdown_after_adverse_move():
    eng = StateEngine(10_000, fee_bps=0)
    eng.on_book(book(1.0, 100, 101))
    eng.apply_fill(10.0, 101.0)
    eng.on_book(book(2.0, 90, 91))
    assert eng.equity == pytest.approx(10_000 - 10 * 101 + 10 * 90.5)
    assert eng.drawdown > 0
    assert eng.snapshot()["dd"] == pytest.approx(eng.drawdown)
