"""Command line: paper replay, synthetic data, and nightly review.

  python -m trading_agent synth events.jsonl -n 2000
  python -m trading_agent paper events.jsonl --log logs/journal.jsonl
  python -m trading_agent review logs/journal.jsonl
"""

import argparse
import json

from .agent import TradingAgent
from .config import Config
from .decision import StubDecisionModel
from .execution import PaperBroker
from .review import Journal, nightly_review
from .risk import RiskLayer
from .state import Book, StateEngine
from .synthetic import write_jsonl


def build_agent(cfg, journal_path=None):
    engine = StateEngine(cfg.starting_equity, depth=cfg.book_depth, window=cfg.vol_window, fee_bps=cfg.fee_bps)
    journal = Journal(journal_path) if journal_path else None
    return TradingAgent(
        engine=engine,
        model=StubDecisionModel(),
        risk=RiskLayer(cfg.limits),
        broker=PaperBroker(),
        journal=journal,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="trading_agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    paper = sub.add_parser("paper", help="replay a JSONL book file through the paper agent")
    paper.add_argument("events")
    paper.add_argument("--log", default="logs/journal.jsonl")

    synth = sub.add_parser("synth", help="write synthetic book events to a JSONL file")
    synth.add_argument("out")
    synth.add_argument("-n", type=int, default=2000)
    synth.add_argument("--seed", type=int, default=0)

    review = sub.add_parser("review", help="print the nightly review for a journal")
    review.add_argument("journal")

    args = parser.parse_args(argv)

    if args.cmd == "synth":
        write_jsonl(args.out, args.n, args.seed)
        print(f"wrote {args.n} events to {args.out}")
        return 0

    if args.cmd == "review":
        print(json.dumps(nightly_review(args.journal), indent=2))
        return 0

    cfg = Config()
    agent = build_agent(cfg, args.log)
    steps = fills = 0
    with open(args.events) as f:
        for line in f:
            if not line.strip():
                continue
            record = agent.step(Book.from_json(json.loads(line)))
            steps += 1
            fills += record["fill"] is not None
    engine = agent.engine
    print(
        f"steps={steps} fills={fills} equity={engine.equity:.2f} "
        f"position={engine.position:.6g} drawdown={engine.drawdown:.4f}"
    )
    print(json.dumps(nightly_review(args.log), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
