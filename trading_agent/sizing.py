"""Position sizing: quarter Kelly on the model's calibrated probability."""


def kelly_fraction(p_win, payoff):
    """Full Kelly fraction of equity. Zero when there is no edge."""
    return max(p_win - (1 - p_win) / payoff, 0.0)


def position_notional(equity, p_win, payoff, limits):
    fraction = min(limits.kelly_multiplier * kelly_fraction(p_win, payoff), limits.max_equity_fraction)
    return min(equity * fraction, limits.max_position_notional)
