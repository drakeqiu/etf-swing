"""ETF日线、项目缓存与严格前复权数据管线。"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

BAR_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


class MarketDataProvider(Protocol):
    def fetch_bars(self, sdk_code: str, start: date, end: date) -> pd.DataFrame: ...

    def fetch_factors(self, sdk_code: str, start: date, end: date) -> pd.DataFrame: ...


def _code_tokens(value: object) -> set[str]:
    parts = str(value).replace("_", ".").replace("-", ".").split(".")
    return {part for part in parts if part}


def resolve_etf_code(symbol: str, code_table: object) -> str:
    """Resolve a bare ETF code against the SDK's EXTRA_ETF table."""
    parts = str(symbol).replace("_", ".").replace("-", ".").split(".")
    target = next((part for part in reversed(parts) if part.isdigit()), symbol)

    if isinstance(code_table, dict):
        values = code_table.keys()
    elif isinstance(code_table, pd.DataFrame):
        values = [
            *code_table.index.tolist(),
            *code_table.astype(str).to_numpy().ravel().tolist(),
        ]
    else:
        values = code_table  # SDK may expose the table as an iterable.
    matches = {str(value) for value in values if target in _code_tokens(value)}
    if len(matches) > 1:
        exchange_codes = {value for value in matches if "." in value}
        if len(exchange_codes) == 1:
            matches = exchange_codes
    if len(matches) != 1:
        raise ValueError(f"ETF code {symbol!r} has {len(matches)} SDK matches")
    return next(iter(matches))


def _sdk_frame(
    result: object,
    sdk_code: str,
    required: list[str],
    aliases: dict[str, str],
) -> pd.DataFrame:
    """Normalize an AmazingData result while rejecting unknown field layouts."""
    if isinstance(result, dict):
        for key in (sdk_code, sdk_code.split(".")[-1]):
            if key in result:
                result = result[key]
                break
    if not isinstance(result, pd.DataFrame):
        raise ValueError("AmazingData query did not return a DataFrame")
    frame = result.copy()
    if isinstance(frame.index, pd.MultiIndex):
        frame = frame.reset_index()
    for column in ("code", "symbol", "security_code", "ticker"):
        if column in frame.columns:
            normalized = sdk_code.upper().replace("_", ".").replace("-", ".")
            frame = frame.loc[frame[column].astype(str).map(
                lambda value: value.upper().replace("_", ".").replace("-", ".") == normalized
            )]
            break
    renames = {
        column: aliases[column.strip().lower()]
        for column in frame.columns
        if column.strip().lower() in aliases
    }
    frame = frame.rename(columns=renames)
    return _dated_frame(frame, required)


_BAR_ALIASES = {
    "date": "Date", "trade_date": "Date", "datetime": "Date",
    "kline_time": "Date", "open": "Open", "high": "High",
    "low": "Low", "close": "Close", "volume": "Volume", "vol": "Volume",
}
_FACTOR_ALIASES = {
    "date": "Date",
    "trade_date": "Date",
    "datetime": "Date",
    "factor": "Factor",
    "adj_factor": "Factor",
    "backward_factor": "Factor",
}


def _dated_frame(frame: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    result = frame.copy()
    if "Date" in result.columns:
        result = result.set_index("Date")
    if pd.api.types.is_integer_dtype(result.index):
        result.index = result.index.astype(str)
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
    """Adapt the local AmazingData code-list, bar, and factor interfaces."""

    def __init__(self, code_table: object, bars_query, factors_query):
        self.code_table = code_table
        self.bars_query = bars_query
        self.factors_query = factors_query

    @classmethod
    def from_sdk(
        cls, base_data: object, market_data: object, *, period: object
    ) -> AmazingDataProvider:
        """Build a provider from AmazingData BaseData and MarketData clients."""
        code_table = base_data.get_code_list(security_type="EXTRA_ETF")

        def bars_query(sdk_code: str, start: date, end: date) -> pd.DataFrame:
            result = market_data.query_kline(
                [sdk_code],
                begin_date=int(start.strftime("%Y%m%d")),
                end_date=int(end.strftime("%Y%m%d")),
                period=period,
            )
            return _sdk_frame(result, sdk_code, BAR_COLUMNS, _BAR_ALIASES)

        def factors_query(sdk_code: str, start: date, end: date) -> pd.DataFrame:
            del start, end
            result = base_data.get_backward_factor([sdk_code], is_local=True)
            if not isinstance(result, pd.DataFrame) or sdk_code not in result.columns:
                raise ValueError(f"Missing backward factor column for {sdk_code}")
            return pd.DataFrame({"Factor": result[sdk_code]}, index=result.index)

        return cls(code_table, bars_query, factors_query)

    def fetch_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        code = resolve_etf_code(symbol, self.code_table)
        return self.bars_query(code, start, end)

    def fetch_factors(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        code = resolve_etf_code(symbol, self.code_table)
        return self.factors_query(code, start, end)


class MarketDataService:
    """管理行情与因子CSV缓存，并返回可回测的前复权数据。"""

    def __init__(self, provider: MarketDataProvider, cache_dir: Path):
        self.provider = provider
        self.cache_dir = Path(cache_dir)
        self.last_metadata: dict[str, object] = {}

    def _path(self, symbol: str) -> Path:
        safe_symbol = "".join(c for c in symbol if c.isalnum() or c in "-_ .")
        return self.cache_dir / f"{safe_symbol}.csv"

    def load(self, symbol: str, start: date, end: date, *, refresh: bool = False) -> pd.DataFrame:
        path = self._path(symbol)
        factor_path = path.with_name(f"{path.stem}.factors.csv")
        if refresh:
            bars = _dated_frame(self.provider.fetch_bars(symbol, start, end), BAR_COLUMNS)
            factors = _dated_frame(self.provider.fetch_factors(symbol, start, end), ["Factor"])
            path.parent.mkdir(parents=True, exist_ok=True)
            bars.to_csv(path, index_label="Date")
            factors.to_csv(factor_path, index_label="Date")
        else:
            if not path.exists() or not factor_path.exists():
                raise FileNotFoundError(f"No complete cached data for {symbol}; use explicit refresh")
            bars = _dated_frame(pd.read_csv(path, parse_dates=["Date"]), BAR_COLUMNS)
            factors = _dated_frame(pd.read_csv(factor_path, parse_dates=["Date"]), ["Factor"])
        first, last = pd.Timestamp(start), pd.Timestamp(end)
        selected = bars.loc[first:last, BAR_COLUMNS]
        missing = pd.bdate_range(first, last).difference(selected.index)
        if selected.empty or len(missing):
            raise ValueError(f"Cached bars do not cover requested trading sessions: {start} to {end}")
        result = adjust_ohlc(selected, factors.loc[selected.index, "Factor"])
        self.last_metadata = {
            "data_coverage_start": selected.index.min().date().isoformat(),
            "data_coverage_end": selected.index.max().date().isoformat(),
            "adjustment_reference_date": selected.index.max().date().isoformat(),
            "cache_status": "refreshed" if refresh else "hit",
        }
        result.attrs.update(self.last_metadata)
        return result
