"""ETF日线、项目缓存与严格前复权数据管线。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

BAR_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


class MarketDataProvider(Protocol):
    """行情适配器必须提供的日线、因子与交易日历数据。"""

    def fetch_bars(
        self, symbol: str, start: date, end: date
    ) -> pd.DataFrame: ...
    def fetch_factors(
        self, symbol: str, start: date, end: date
    ) -> pd.DataFrame: ...
    def trading_sessions(self, start: date, end: date) -> pd.DatetimeIndex: ...


def _code_tokens(value: object) -> set[str]:
    parts = str(value).replace("_", ".").replace("-", ".").split(".")
    return {part for part in parts if part}


def resolve_etf_code(symbol: str, code_table: Any) -> str:
    """依据 AmazingData 的 EXTRA_ETF 代码表解析 ETF 代码。"""
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
        values = code_table  # SDK 也可能返回可迭代的代码表。
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
    """规范化 AmazingData 查询结果；字段布局不明时明确失败。"""
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
    expected_digits = {
        token for token in _code_tokens(sdk_code) if token.isdigit()
    }

    def same_code(value: object) -> bool:
        actual_tokens = _code_tokens(value)
        actual_digits = {token for token in actual_tokens if token.isdigit()}
        if expected_digits and actual_digits:
            return expected_digits == actual_digits
        normalized = str(value).upper().replace("_", ".").replace("-", ".")
        expected = sdk_code.upper().replace("_", ".").replace("-", ".")
        return normalized == expected

    for column in ("code", "symbol", "security_code", "ticker"):
        if column in frame.columns:
            frame = frame.loc[frame[column].map(same_code)]
            break
    renames = {
        column: aliases[column.strip().lower()]
        for column in frame.columns
        if column.strip().lower() in aliases
    }
    frame = frame.rename(columns=renames)
    return _dated_frame(frame, required).loc[:, required]


_BAR_ALIASES = {
    "date": "Date",
    "trade_date": "Date",
    "datetime": "Date",
    "kline_time": "Date",
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume",
    "vol": "Volume",
}

def _normalized_datetime_index(values: Any) -> pd.DatetimeIndex:
    dates = pd.to_datetime(pd.Series(values), errors="raise")
    return pd.DatetimeIndex(dates.dt.normalize())


def _dated_frame(frame: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    result = frame.copy()
    if "Date" in result.columns:
        result = result.set_index("Date")
    if pd.api.types.is_integer_dtype(result.index):
        result.index = result.index.astype(str)
    result.index = _normalized_datetime_index(result.index)
    result.index.name = "Date"
    missing = set(required).difference(result.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(sorted(missing))}"
        )
    if result.index.has_duplicates:
        raise ValueError("Duplicate dates are not allowed")
    return result.sort_index()


def adjust_ohlc(bars: pd.DataFrame, factors: pd.Series) -> pd.DataFrame:
    """按因子与区间最新因子之比调整 OHLC，不填充日期。"""
    data = _dated_frame(bars, BAR_COLUMNS)
    factor_series = factors.copy()
    factor_series.index = _normalized_datetime_index(factor_series.index)
    factor_series = factor_series.sort_index()
    if factor_series.index.has_duplicates:
        raise ValueError("Duplicate factor dates are not allowed")
    if not factor_series.index.equals(data.index):
        raise ValueError("Factor dates must strictly match every bar date")
    aligned = factor_series
    if aligned.isna().any():
        raise ValueError("Factor dates must strictly match every bar date")
    if not (aligned > 0).all():
        raise ValueError("Factors must be positive")
    ratio = aligned / aligned.iloc[-1]
    ohlc_columns = ["Open", "High", "Low", "Close"]
    adjusted = data[ohlc_columns].astype(float).mul(ratio, axis=0)
    data = data.astype({column: float for column in ohlc_columns})
    data.loc[:, ohlc_columns] = adjusted
    return data.loc[:, BAR_COLUMNS]


class AmazingDataProvider:
    """适配 AmazingData 的 ETF 代码表、日线与复权因子接口。"""

    def __init__(
        self,
        code_table: Any,
        bars_query: Callable[[str, date, date], pd.DataFrame],
        factors_query: Callable[[str, date, date], pd.DataFrame],
        calendar: Any = None,
    ):
        """保存代码表与三类数据查询回调。"""
        self.code_table = code_table
        self.bars_query = bars_query
        self.factors_query = factors_query
        self.calendar = calendar

    @classmethod
    def from_sdk(
        cls,
        base_data: Any,
        market_data: Any,
        *,
        period: int,
        calendar: Any = None,
    ) -> AmazingDataProvider:
        """使用 AmazingData 客户端构建数据提供器。"""
        code_table = base_data.get_code_list(security_type="EXTRA_ETF")
        if calendar is None:
            calendar = base_data.get_calendar()

        def bars_query(sdk_code: str, start: date, end: date) -> pd.DataFrame:
            result = market_data.query_kline(
                [sdk_code],
                begin_date=int(start.strftime("%Y%m%d")),
                end_date=int(end.strftime("%Y%m%d")),
                period=period,
            )
            return _sdk_frame(result, sdk_code, BAR_COLUMNS, _BAR_ALIASES)

        def factors_query(
            sdk_code: str, start: date, end: date
        ) -> pd.DataFrame:
            del start, end
            result = base_data.get_backward_factor([sdk_code], is_local=True)
            if (
                not isinstance(result, pd.DataFrame)
                or sdk_code not in result.columns
            ):
                raise ValueError(
                    f"Missing backward factor column for {sdk_code}"
                )
            factors = pd.DataFrame(
                {"Factor": result[sdk_code]}, index=result.index
            )
            return _dated_frame(factors, ["Factor"])

        return cls(code_table, bars_query, factors_query, calendar)

    def fetch_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """按代码表映射标的后查询并标准化日线数据。"""
        code = resolve_etf_code(symbol, self.code_table)
        return self.bars_query(code, start, end)

    def fetch_factors(
        self, symbol: str, start: date, end: date
    ) -> pd.DataFrame:
        """查询并返回按交易日索引的后复权因子。"""
        code = resolve_etf_code(symbol, self.code_table)
        return self.factors_query(code, start, end)

    def trading_sessions(self, start: date, end: date) -> pd.DatetimeIndex:
        """返回 AmazingData 日历中落入请求区间的交易日。"""
        values = self.calendar
        if isinstance(values, pd.DataFrame):
            values = values.iloc[:, 0].tolist()
        raw = pd.Series(values)
        if pd.api.types.is_numeric_dtype(raw):
            sessions = pd.to_datetime(
                raw.astype(str), format="%Y%m%d", errors="coerce"
            )
        else:
            sessions = pd.to_datetime(raw, errors="coerce")
        sessions = sessions.dropna().dt.normalize()
        mask = sessions.between(pd.Timestamp(start), pd.Timestamp(end))
        return pd.DatetimeIndex(sessions.loc[mask])


class MarketDataService:
    """管理行情与因子CSV缓存，并返回可回测的前复权数据。"""

    def __init__(self, provider: MarketDataProvider, cache_dir: Path):
        """配置数据提供器与运行时缓存目录。"""
        self.provider = provider
        self.cache_dir = Path(cache_dir)
        self.last_metadata: dict[str, object] = {}

    def _path(self, symbol: str) -> Path:
        safe_symbol = "".join(c for c in symbol if c.isalnum() or c in "-_ .")
        return self.cache_dir / f"{safe_symbol}.csv"

    def load(
        self, symbol: str, start: date, end: date, *, refresh: bool = False
    ) -> pd.DataFrame:
        """读取完整区间缓存；仅在 refresh=True 时更新行情和因子。"""
        path = self._path(symbol)
        factor_path = path.with_name(f"{path.stem}.factors.csv")
        sessions_path = path.with_name(f"{path.stem}.sessions.csv")
        if refresh:
            bars = _dated_frame(
                self.provider.fetch_bars(symbol, start, end), BAR_COLUMNS
            )
            factors = _dated_frame(
                self.provider.fetch_factors(symbol, start, end), ["Factor"]
            )
            if hasattr(self.provider, "trading_sessions"):
                sessions = self.provider.trading_sessions(start, end)
            else:
                sessions = pd.bdate_range(start, end)
            sessions = (
                _normalized_datetime_index(sessions).unique().sort_values()
            )
            coverage_start, coverage_end = (
                pd.Timestamp(start),
                pd.Timestamp(end),
            )
        else:
            if (
                not path.exists()
                or not factor_path.exists()
                or not sessions_path.exists()
            ):
                raise FileNotFoundError(
                    f"No complete cache for {symbol}; use --refresh"
                )
            bars = _dated_frame(
                pd.read_csv(path, parse_dates=["Date"]), BAR_COLUMNS
            )
            factors = _dated_frame(
                pd.read_csv(factor_path, parse_dates=["Date"]), ["Factor"]
            )
            session_frame = pd.read_csv(sessions_path, parse_dates=["Date"])
            sessions = _normalized_datetime_index(session_frame["Date"])
            coverage_start = pd.Timestamp(
                session_frame["coverage_start"].iloc[0]
            )
            coverage_end = pd.Timestamp(session_frame["coverage_end"].iloc[0])
        first, last = pd.Timestamp(start), pd.Timestamp(end)
        if not isinstance(first, pd.Timestamp) or not isinstance(
            last, pd.Timestamp
        ):
            raise ValueError("Requested interval boundaries must be valid")
        if not isinstance(coverage_start, pd.Timestamp) or not isinstance(
            coverage_end, pd.Timestamp
        ):
            raise ValueError("Cached coverage boundaries must be valid")
        if first < coverage_start or last > coverage_end:
            raise ValueError(
                f"Cache does not cover requested interval {start} to {end}"
            )
        selected = bars.loc[first:last, BAR_COLUMNS]
        expected = sessions[(sessions >= first) & (sessions <= last)]
        selected_index = pd.DatetimeIndex(selected.index)
        missing = expected.difference(selected_index)
        unexpected = selected_index.difference(expected)
        if selected.empty or expected.empty or len(missing) or len(unexpected):
            raise ValueError(
                "Cached bars do not cover requested trading sessions: "
                f"{start} to {end}"
            )
        requested_factors = factors.loc[first:last, "Factor"]
        result = adjust_ohlc(selected, requested_factors)
        if refresh:
            path.parent.mkdir(parents=True, exist_ok=True)
            bars.to_csv(path, index_label="Date")
            factors.to_csv(factor_path, index_label="Date")
            pd.DataFrame(
                {
                    "Date": sessions,
                    "coverage_start": start.isoformat(),
                    "coverage_end": end.isoformat(),
                }
            ).to_csv(sessions_path, index=False)
        self.last_metadata = {
            "data_coverage_start": selected.index.min().date().isoformat(),
            "data_coverage_end": selected.index.max().date().isoformat(),
            "adjustment_reference_date": selected.index.max()
            .date()
            .isoformat(),
            "cache_status": "refreshed" if refresh else "hit",
        }
        result.attrs.update(self.last_metadata)
        return result
