"""SMA strategy and deterministic backtesting.py execution helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backtesting import Backtest, Strategy

if TYPE_CHECKING:
    import pandas as pd

INITIAL_CASH = 100_000
LOT_SIZE = 100
COMMISSION_RATE = 0.00005
MIN_COMMISSION = 0.1
DEFAULT_SPREAD = 0.0005


def commission(size: float, price: float) -> float:
    """Return one-side commission, enforcing the per-fill minimum."""
    return max(abs(size) * price * COMMISSION_RATE, MIN_COMMISSION)


def sma(values: object, period: int) -> object:
    """Compute a trailing simple moving average for backtesting.py."""
    import numpy as np

    result = np.full(len(values), np.nan)
    for index in range(period - 1, len(values)):
        result[index] = np.mean(values[index - period + 1 : index + 1])
    return result


class SmaCross(Strategy):
    """Long when SMA(20) exceeds SMA(60), otherwise flat."""

    def init(self) -> None:
        self.fast = self.I(sma, self.data.Close, 20)
        self.slow = self.I(sma, self.data.Close, 60)

    def next(self) -> None:
        if self.fast[-1] > self.slow[-1]:
            if not self.position:
                size = int(self.equity / self.data.Close[-1] / LOT_SIZE) * LOT_SIZE
                if size:
                    self.buy(size=size)
        elif self.position:
            self.position.close()


def run_backtest(data: pd.DataFrame, spread: float = DEFAULT_SPREAD):
    """Run the long/flat strategy with project execution assumptions."""
    backtest = Backtest(
        data,
        SmaCross,
        cash=INITIAL_CASH,
        commission=commission,
        spread=spread,
        exclusive_orders=True,
        finalize_trades=True,
    )
    return backtest.run()
