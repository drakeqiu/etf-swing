"""Typing surface consumed from the untyped backtesting.py distribution."""

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

class _Data:
    Close: np.ndarray[Any, Any]

class Order: ...

class Position:
    def __bool__(self) -> bool: ...
    def close(self, portion: float = ...) -> None: ...

class Strategy:
    data: _Data
    equity: float
    position: Position

    def I(  # noqa: E743
        self,
        func: Callable[..., Any],
        *args: Any,
        name: Any = ...,
        plot: bool = ...,
        overlay: bool | None = ...,
        color: str | None = ...,
        scatter: bool = ...,
        **kwargs: Any,
    ) -> np.ndarray[Any, Any]: ...
    def buy(
        self,
        *,
        size: float = ...,
        limit: float | None = ...,
        stop: float | None = ...,
        sl: float | None = ...,
        tp: float | None = ...,
        tag: object = ...,
    ) -> Order: ...
    def init(self) -> None: ...
    def next(self) -> None: ...

class Backtest:
    def __init__(
        self,
        data: pd.DataFrame,
        strategy: type[Strategy],
        *,
        cash: float = ...,
        spread: float = ...,
        commission: float | tuple[float, float] | Callable[..., float] = ...,
        margin: float = ...,
        trade_on_close: bool = ...,
        hedging: bool = ...,
        exclusive_orders: bool = ...,
        finalize_trades: bool = ...,
    ) -> None: ...
    def run(self, **kwargs: Any) -> pd.Series: ...
