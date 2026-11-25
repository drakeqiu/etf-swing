from __future__ import annotations

import numpy as np
import pandas as pd

from etf_swing.backtest import commission, run_backtest


def synthetic_data() -> pd.DataFrame:
    close = np.array([100.0] * 75 + list(np.linspace(101, 180, 45)) +
                     [180.0] * 20 + list(np.linspace(179, 70, 65)))
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1,
         "Close": close, "Volume": 1_000_000},
        index=pd.date_range("2025-01-01", periods=len(close), freq="B"),
    )


def test_commission_proportional_and_minimum() -> None:
    assert commission(100, 100) == 0.5
    assert commission(100, 10) == 0.1


def test_strategy_executes_signals_on_next_bar_and_closes() -> None:
    data = synthetic_data()
    trades = run_backtest(data, spread=0)["_trades"]

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade.EntryBar > 0
    assert trade.EntryPrice == data.Open.iloc[trade.EntryBar]
    assert trade.ExitBar > trade.EntryBar
    assert trade.ExitPrice == data.Open.iloc[trade.ExitBar]
    assert trade.Size % 100 == 0
    assert trade.Commission > 0


def test_commission_is_charged_on_both_sides() -> None:
    trade = run_backtest(synthetic_data(), spread=0)["_trades"].iloc[0]
    expected = max(abs(trade.Size) * trade.EntryPrice * 0.00005, 0.1)
    expected += max(abs(trade.Size) * trade.ExitPrice * 0.00005, 0.1)
    assert trade.Commission == expected
