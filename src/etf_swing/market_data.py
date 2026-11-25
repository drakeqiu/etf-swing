"""ETF daily bars, local cache, and strict forward adjustment."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd

BAR_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


class MarketDataProvider(Protocol):
    def fetch_bars(self, sdk_code: str, start: date, end: date) -> pd.DataFrame: ...

    def fetch_factors(self, sdk_code: str, start: date, end: date) -> pd.DataFrame: ...


def resolve_etf_code(symbol: str, code_table: object) -> str:
    """Resolve a bare ETF code against the SDK's EXTRA_ETF table."""
    target = symbol.split(".", maxsplit=1)[0]
    if isinstance(code_table, dict):
        entries = code_table.keys()
    elif isinstance(code_table, pd.DataFrame):
        entries = code_table.iloc[:, 0].astype(str)
    else:
        entries = code_table  # SDK may expose the table as an iterable.
    matches = [str(code) for code in entries if str(code).split(".", 1)[0] == target]
    if len(matches) != 1:
        raise ValueError(f"ETF code {symbol!r} has {len(matches)} SDK matches")
    return matches[0]


def _dated_frame(frame: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    result = frame.copy()
    if "Date" in result.columns:
        result = result.set_index("Date")
    result.index = pd.to_datetime(result.index, errors="raise").normalize()
    result.index.name = "Date"
    missing = set(required).difference(result.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if result.index.has_duplicates:
        raise ValueError("Duplicate dates are not allowed")
    return result.sort_index()


def adjust_ohlc(bars: pd.DataFrame, factors: pd.Series) -> pd.DataFrame:
    """Adjust OHLC by factor/date-range-latest-factor, without filling dates."""
    data = _dated_frame(bars, BAR_COLUMNS)
    factor_series = factors.copy()
    factor_series.index = pd.to_datetime(factor_series.index, errors="raise").normalize()
    factor_series = factor_series.sort_index()
    if factor_series.index.has_duplicates:
        raise ValueError("Duplicate factor dates are not allowed")
    aligned = factor_series.reindex(data.index)
    if aligned.isna().any():
        raise ValueError("Factor dates must strictly match every bar date")
    if not (aligned > 0).all():
        raise ValueError("Factors must be positive")
    ratio = aligned / aligned.iloc[-1]
    data.loc[:, ["Open", "High", "Low", "Close"]] = data[
        ["Open", "High", "Low", "Close"]
    ].mul(ratio, axis=0)
    return data[BAR_COLUMNS]


class AmazingDataProvider:
    """Adapter over SDK code table and injected SDK query callables."""

    def __init__(self, code_table: object, bars_query, factors_query):
        self.code_table = code_table
        self.bars_query = bars_query
        self.factors_query = factors_query

    def fetch_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        return self.bars_query(resolve_etf_code(symbol, self.code_table), start, end)

    def fetch_factors(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        return self.factors_query(resolve_etf_code(symbol, self.code_table), start, end)


class MarketDataService:
    def __init__(self, provider: MarketDataProvider, cache_dir: Path):
        self.provider = provider
        self.cache_dir = Path(cache_dir)

    def _path(self, symbol: str) -> Path:
        safe_symbol = "".join(c for c in symbol if c.isalnum() or c in "-_ .")
        return self.cache_dir / f"{safe_symbol}.csv"

    def load(self, symbol: str, start: date, end: date, *, refresh: bool = False) -> pd.DataFrame:
        path = self._path(symbol)
        if refresh:
            bars = _dated_frame(self.provider.fetch_bars(symbol, start, end), BAR_COLUMNS)
            path.parent.mkdir(parents=True, exist_ok=True)
            bars.to_csv(path, index_label="Date")
        else:
            if not path.exists():
                raise FileNotFoundError(f"No cached bars for {symbol}; use explicit refresh")
            bars = _dated_frame(pd.read_csv(path, parse_dates=["Date"]), BAR_COLUMNS)
        first, last = pd.Timestamp(start), pd.Timestamp(end)
        if bars.empty or bars.index.min() > first or bars.index.max() < last:
            raise ValueError(f"Cached bars do not cover requested interval {start} to {end}")
        bars = bars.loc[first:last, BAR_COLUMNS]
        factor_frame = _dated_frame(
            self.provider.fetch_factors(symbol, start, end), ["Factor"]
        )
        return adjust_ohlc(bars, factor_frame["Factor"])
