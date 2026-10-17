"""Synthetic order book generator for paper runs and tests. Not market data."""

import json
import random


def generate(n, seed=0, start_ticks=10_000, depth=5):
    """Yield n book events as dicts. Prices are integer ticks of 0.01."""
    rng = random.Random(seed)
    px = start_ticks
    for i in range(n):
        px = max(500, px + rng.randint(-5, 5))
        spread = rng.randint(1, 3)
        bid_top = px - spread // 2
        ask_top = bid_top + spread
        yield {
            "ts": float(i),
            "bids": [[round((bid_top - j) / 100, 2), round(rng.uniform(1, 10), 3)] for j in range(depth)],
            "asks": [[round((ask_top + j) / 100, 2), round(rng.uniform(1, 10), 3)] for j in range(depth)],
        }


def write_jsonl(path, n, seed=0):
    with open(path, "w") as f:
        for row in generate(n, seed):
            f.write(json.dumps(row) + "\n")
