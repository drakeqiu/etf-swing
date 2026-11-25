"""SMA策略与确定性的 backtesting.py 执行工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from backtesting import Backtest, Strategy

if TYPE_CHECKING:
    import pandas as pd

FAST_SMA_PERIOD = 20
SLOW_SMA_PERIOD = 60

INITIAL_CASH = 100_000
LOT_SIZE = 100
COMMISSION_RATE = 0.00005
MIN_COMMISSION = 0.1
DEFAULT_SPREAD = 0.0005


def commission(size: float, price: float) -> float:
    """Return one-side commission, enforcing the per-fill minimum."""
    return max(abs(size) * price * COMMISSION_RATE, MIN_COMMISSION)


def sma(values: object, period: int) -> object:
    """计算 backtesting.py 所需的移动平均序列。"""
    result = np.full(len(values), np.nan)
    for index in range(period - 1, len(values)):
        result[index] = np.mean(values[index - period + 1 : index + 1])
    return result


class SmaCross(Strategy):
    """快线高于慢线时持有多头，否则保持空仓。"""

    def init(self) -> None:
        self.fast = self.I(sma, self.data.Close, FAST_SMA_PERIOD)
        self.slow = self.I(sma, self.data.Close, SLOW_SMA_PERIOD)

    def next(self) -> None:
        if self.fast[-1] > self.slow[-1]:
            if not self.position:
                price_with_costs = self.data.Close[-1] * (1 + DEFAULT_SPREAD)
                affordable = self.equity / (price_with_costs * (1 + COMMISSION_RATE))
                size = int(affordable / LOT_SIZE) * LOT_SIZE
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
    )
    return backtest.run()
