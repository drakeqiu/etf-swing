from __future__ import annotations


from etf_swing.backtest import commission, run_backtest
from synthetic_data import synthetic_data
def test_commission_proportional_and_minimum() -> None:
    assert commission(100, 100) == 0.5
    assert commission(100, 10) == 0.1


def test_position_sizing_accounts_for_spread_and_commission() -> None:
    trade = run_backtest(synthetic_data(), spread=0.02)["_trades"].iloc[0]
    purchase_cost = abs(trade.Size) * trade.EntryPrice * 1.02
    entry_commission = max(abs(trade.Size) * trade.EntryPrice * 0.00005, 0.1)
    assert purchase_cost + entry_commission <= 100_000


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
