"""Journaling and the nightly review: calibration and action counts from the log."""

import json
from collections import Counter
from pathlib import Path


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record):
        with self.path.open("a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")


def brier_score(pairs):
    """Mean squared error between predicted win probability and the 0/1 outcome."""
    if not pairs:
        return None
    return sum((p - (1.0 if won else 0.0)) ** 2 for p, won in pairs) / len(pairs)


def nightly_review(path):
    lines = Path(path).read_text().splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    steps = [r for r in records if r.get("type") == "step"]
    outcomes = [(r["p_win"], r["won"]) for r in records if r.get("type") == "outcome"]
    confidences = [r["decision"]["confidence"] for r in steps if r["decision"] is not None]
    return {
        "steps": len(steps),
        "actions": dict(Counter(r["action"] for r in steps)),
        "reasons": dict(Counter(r["reason"] for r in steps)),
        "fills": sum(1 for r in steps if r["fill"] is not None),
        "closed_trades": len(outcomes),
        "win_rate": (sum(won for _, won in outcomes) / len(outcomes)) if outcomes else None,
        "brier": brier_score(outcomes),
        "mean_confidence": (sum(confidences) / len(confidences)) if confidences else None,
    }
