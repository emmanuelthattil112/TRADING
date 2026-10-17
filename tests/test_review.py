import pytest

from trading_agent.review import Journal, brier_score, nightly_review


def test_brier_perfect_and_worst():
    assert brier_score([(1.0, True), (0.0, False)]) == 0.0
    assert brier_score([(1.0, False), (0.0, True)]) == 1.0


def test_brier_known_value():
    # (0.6 - 1)^2 = 0.16 and (0.6 - 0)^2 = 0.36; mean is 0.26
    assert brier_score([(0.6, True), (0.6, False)]) == pytest.approx(0.26)


def test_brier_empty_is_none():
    assert brier_score([]) is None


def test_nightly_review_reads_journal(tmp_path):
    journal = Journal(tmp_path / "j.jsonl")
    journal.write({"type": "step", "action": "hold", "reason": "confidence", "fill": None,
                   "decision": {"confidence": 0.7}})
    journal.write({"type": "step", "action": "enter_long", "reason": "entry", "fill": {"qty": 1},
                   "decision": {"confidence": 0.9}})
    journal.write({"type": "outcome", "p_win": 0.8, "won": True})
    report = nightly_review(tmp_path / "j.jsonl")
    assert report["steps"] == 2
    assert report["fills"] == 1
    assert report["closed_trades"] == 1
    assert report["actions"] == {"hold": 1, "enter_long": 1}
    assert report["mean_confidence"] == pytest.approx(0.8)
    assert report["brier"] == pytest.approx(0.04)
