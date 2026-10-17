import json
from dataclasses import replace

import pytest

from trading_agent.__main__ import build_agent, main
from trading_agent.agent import TradingAgent
from trading_agent.config import Config, RiskLimits
from trading_agent.decision import StubDecisionModel
from trading_agent.execution import PaperBroker
from trading_agent.review import Journal, nightly_review
from trading_agent.risk import RiskLayer
from trading_agent.schema import Decision, DecisionError
from trading_agent.state import Book, StateEngine
from trading_agent.synthetic import generate


class FixedModel:
    def __init__(self, decision):
        self.decision = decision

    def decide(self, snap):
        return self.decision


class RaisingModel:
    def decide(self, snap):
        raise DecisionError("bad output")


def bullish_decision():
    return Decision(
        regime="trending",
        direction="long",
        toxic_flow=False,
        setup_quality=3,
        risk_state="safe",
        confidence=0.9,
        p_win=0.6,
        payoff=1.0,
    )


def book(ts, bid=100.0, ask=101.0):
    return Book(ts=ts, bids=((bid, 50.0), (bid - 1, 50.0)), asks=((ask, 50.0), (ask + 1, 50.0)))


def make_agent(tmp_path, model, escalator=None, journal=True, **limits):
    limits.setdefault("kill_switch_file", tmp_path / "KILL")
    engine = StateEngine(10_000, fee_bps=0)
    j = Journal(tmp_path / "journal.jsonl") if journal else None
    return TradingAgent(
        engine=engine,
        model=model,
        risk=RiskLayer(RiskLimits(**limits)),
        broker=PaperBroker(),
        escalator=escalator,
        journal=j,
    )


def test_order_decided_on_one_book_fills_on_the_next(tmp_path):
    agent = make_agent(tmp_path, FixedModel(bullish_decision()))
    first = agent.step(book(1.0))
    assert first["action"] == "enter_long"
    assert first["fill"] is None
    assert agent.engine.position == 0.0

    second = agent.step(book(2.0))
    assert second["fill"] is not None
    assert second["fill"]["price"] == 101.0
    assert agent.engine.position > 0


def test_entry_and_exit_produce_a_journaled_outcome(tmp_path):
    agent = make_agent(tmp_path, FixedModel(bullish_decision()))
    agent.step(book(1.0))
    agent.step(book(2.0))  # fill entry at ask 101
    agent.model = FixedModel(replace(bullish_decision(), direction="short"))
    agent.step(book(3.0, bid=110.0, ask=111.0))  # opposing signal, flatten decided
    agent.step(book(4.0, bid=110.0, ask=111.0))  # flatten filled at bid 110
    assert agent.engine.position == 0.0
    review = nightly_review(tmp_path / "journal.jsonl")
    assert review["closed_trades"] == 1
    assert review["win_rate"] == 1.0


def test_crisis_without_escalator_never_opens_a_position(tmp_path):
    crisis = replace(bullish_decision(), regime="crisis")
    agent = make_agent(tmp_path, FixedModel(crisis))
    record = agent.step(book(1.0))
    assert record["action"] == "hold"
    assert record["reason"] == "escalation_unavailable"


def test_escalator_result_is_used_when_it_resolves(tmp_path):
    crisis = replace(bullish_decision(), regime="crisis")
    agent = make_agent(tmp_path, FixedModel(crisis), escalator=FixedModel(bullish_decision()))
    record = agent.step(book(1.0))
    assert record["source"] == "escalated"
    assert record["action"] == "enter_long"


def test_invalid_model_output_holds(tmp_path):
    agent = make_agent(tmp_path, RaisingModel())
    record = agent.step(book(1.0))
    assert record["source"] == "invalid"
    assert record["action"] == "hold"


def test_kill_switch_flattens_during_live_run(tmp_path):
    agent = make_agent(tmp_path, FixedModel(bullish_decision()))
    agent.step(book(1.0))
    agent.step(book(2.0))
    assert agent.engine.position > 0
    (tmp_path / "KILL").write_text("stop")
    agent.step(book(3.0))
    agent.step(book(4.0))
    assert agent.engine.position == 0.0


def test_equity_identity_holds_over_synthetic_run(tmp_path):
    cfg = Config()
    agent = build_agent(cfg, tmp_path / "journal.jsonl")
    for row in generate(500, seed=7):
        agent.step(Book.from_json(row))
        eng = agent.engine
        assert eng.equity == pytest.approx(eng.cash + eng.position * eng.mid)


def test_cli_paper_run_end_to_end(tmp_path, capsys):
    events = tmp_path / "events.jsonl"
    assert main(["synth", str(events), "-n", "300", "--seed", "1"]) == 0
    log = tmp_path / "journal.jsonl"
    assert main(["paper", str(events), "--log", str(log)]) == 0
    out = capsys.readouterr().out
    assert "steps=300" in out
    assert json.loads(out[out.index("{"):])["steps"] == 300
