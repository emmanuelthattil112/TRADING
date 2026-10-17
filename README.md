# trading-agent

A paper-trading agent for crypto order books. It has a deterministic state engine, a validated decision schema, a risk layer that the decision model cannot override, quarter-Kelly sizing, a paper broker, a journal, and a nightly review.

**There is no live order routing.** The broker is paper only, and the code has no path to a real exchange. Nothing here is a profitable strategy. The included decision model is a placeholder.

## What is built

| Module | Role |
| --- | --- |
| `trading_agent/state.py` | Order book in, one compact numeric snapshot out. Rejects out-of-order events and crossed or unsorted books. Each snapshot uses only events up to its own timestamp. |
| `trading_agent/schema.py` | `Decision` dataclass. Every model output is validated before use. Invalid output becomes a hold. |
| `trading_agent/risk.py` | Hard limits applied in code after every model output. Kill switch, drawdown, daily loss, escalation, confidence and setup gates, no pyramiding. |
| `trading_agent/sizing.py` | Quarter Kelly on the calibrated `p_win`, capped at a fraction of equity and a notional ceiling. |
| `trading_agent/decision.py` | `DecisionModel` protocol and a `StubDecisionModel` placeholder. |
| `trading_agent/execution.py` | `PaperBroker`. Taker fills walk the book, partial fills when depth runs out, fee in bps. |
| `trading_agent/agent.py` | Tick loop. An order decided on book t fills on book t+1. Escalation path. Journals every step and every closed trade. |
| `trading_agent/review.py` | JSONL journal and nightly review: action counts, reasons, win rate, Brier score. |
| `trading_agent/synthetic.py` | Random-walk book generator for smoke runs. This is not market data. |

## Run it

```bash
# from the repo root; needs Python 3.11+ and pytest for the tests
python -m pip install pytest
python -m pytest -q

python -m trading_agent synth events.jsonl -n 3000 --seed 42
python -m trading_agent paper events.jsonl --log logs/journal.jsonl
python -m trading_agent review logs/journal.jsonl
```

Events are JSON lines: `{"ts": <float>, "bids": [[price, size], ...], "asks": [[price, size], ...]}`, best level first.

To halt everything, create a file named `KILL` in the working directory. Entries stop, and any open position is flattened on the next book. Remove the file to resume.

## Limits (`trading_agent/config.py`)

| Limit | Default | Effect |
| --- | --- | --- |
| `max_drawdown` | 0.15 | Flatten and halt at 15% below peak equity |
| `max_daily_loss` | 100 | Flatten and halt for the day. Call `StateEngine.new_day()` to reset it. |
| `max_position_notional` | 1000 | Per-trade notional ceiling |
| `max_equity_fraction` | 0.10 | Per-trade cap as a fraction of equity |
| `min_confidence` | 0.80 | No entry below this |
| `escalate_confidence` | 0.60 | Escalate below this, or on regime `crisis` |
| `min_setup_quality` | 2 | No entry below this |
| `kelly_multiplier` | 0.25 | Quarter Kelly |

## Interpretation choices

These are my readings of the spec, not facts. Change them if they're wrong.

- **Quarter Kelly** is read as `0.25 × full Kelly`, where full Kelly is `p − (1−p)/b`. It is then capped by the per-trade and notional limits.
- **Escalation without an escalator** does not hold silently. The agent flattens any open position and does not open one. Crisis or low confidence should not leave money exposed while nothing is reviewing it.
- **Exits are not gated by confidence.** An opposing signal flattens a position whatever its confidence, because exits reduce risk.
- **Kill switch** blocks entries and flattens. It does not wait for a human to flatten by hand.
- **One position at a time.** No adding to a position, and no direct flip. A reversal happens as a flatten, then a later entry.
- **Fill timing.** Orders decided on book t fill on book t+1, at the book's walked VWAP. Orders are not filled on the book they were decided from.

## What is not built

The spec asked for more than this. The following are missing, and I did not fake them:

- **AgenKit at agenkit.xyz.** I did not install or verify it. It is an external tool that I could not check, and installing it is your decision.
- **The "Jev" decision model** at console.typesafe.ai. There is no adapter, because I don't know its API and I have no key. The `DecisionModel` protocol is where it plugs in, and it must return a validated `Decision`.
- **The Opus escalation model.** `TradingAgent` accepts an `escalator`, but none is wired up.
- **The research layer.** The 5 to 10 asymmetric setups with sources, supply and unlock data, and bear cases need live primary-source data that I did not gather. I did not write them from memory, because that would mean inventing metrics.
- **Live execution.** There is no live broker, by design, until you review paper results and decide otherwise.
- **The six-phase approval gates.** These are process steps for building with AgenKit. They are not in the code.
- **The self-improvement loop.** The journal and Brier score exist. Nothing rewrites the decision schema automatically.

## WHAT COULD I BE WRONG ABOUT?

- **There is probably no edge.** The stub's signal is order-book imbalance, which is a weak and well-known signal. Its confidence is usually below the escalation threshold, so in the synthetic run most steps escalate and hold. The synthetic data is a random walk, so no result from it says anything about markets.
- **The catalyst may already be priced in.** Nothing here checks whether a setup was public long before the agent sees it.
- **Value may not accrue to the token.** The research layer, which would test this, is not built.
- **Costs are optimistic.** Slippage is the walked book only. Latency, queue position, our own market impact, funding, and exchange outages are not modelled. Real fills will be worse.
- **Probabilities may be miscalibrated.** Kelly sizing is only as good as `p_win`, and a model's confidence is not its calibration. The Brier score in the nightly review is the only check, and it needs many closed trades before it means anything.
- **Some hard limits are delegated to a file.** The kill switch is a file on disk. If the process cannot see that path, or the file is deleted, the switch does nothing. The drawdown and daily-loss limits reset only when the caller says so. Nothing stops a caller from resetting them too often.
- **Daily loss is not reset automatically.** `new_day()` must be called by whatever runs the agent.
- **The stub's thresholds are arbitrary.** The volatility and spread cut-offs were chosen by hand and not calibrated to anything.
- **Survival before profit.** The limits here are about not losing badly. They say nothing about making money, and a system that survives can still just break even minus fees.

Before any of this touches real money, you would need: a real decision model with out-of-sample results, real exchange data, a live broker with its own tests, and weeks of paper results you have actually reviewed.
