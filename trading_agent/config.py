"""Hard limits for the trading agent.

The decision model never reads or edits these. They are applied in code after
every model output, so a model cannot widen them.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RiskLimits:
    max_drawdown: float = 0.15  # flatten and halt at 15% below peak equity
    max_daily_loss: float = 100.0  # quote currency; flatten and halt for the day
    max_position_notional: float = 1_000.0
    max_equity_fraction: float = 0.10  # per-trade cap as a fraction of equity
    min_confidence: float = 0.80  # no entry below this
    escalate_confidence: float = 0.60  # escalate for a deep re-read below this
    min_setup_quality: int = 2
    kelly_multiplier: float = 0.25  # quarter Kelly
    kill_switch_file: Path = Path("KILL")  # creating this file halts everything


@dataclass(frozen=True)
class Config:
    starting_equity: float = 10_000.0
    fee_bps: float = 10.0
    book_depth: int = 5
    vol_window: int = 50
    limits: RiskLimits = field(default_factory=RiskLimits)
