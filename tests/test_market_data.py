from datetime import date

import pandas as pd
import pytest

from etf_swing.market_data import (
    AmazingDataProvider,
    MarketDataService,
    adjust_ohlc,
    resolve_etf_code,
)


class FakeProvider:
    def __init__(self):
        self.market_calls = 0

    def fetch_bars(self, sdk_code, start, end):
        self.market_calls += 1
        return pd.DataFrame(
            {
                "Date": ["2024-01-02", "2024-01-03"],
                "Open": [10.0, 11.0],
                "High": [12.0, 13.0],
                "Low": [9.0, 10.0],
                "Close": [11.0, 12.0],
                "Volume": [100, 200],
            }
        )

    def fetch_factors(self, sdk_code, start, end):
        return pd.DataFrame(
            {"Date": ["2024-01-02", "2024-01-03"], "Factor": [2.0, 4.0]}
        )


def test_resolves_etf_and_adapter_queries_sdk_code():
    queried = []
    adapter = AmazingDataProvider(
        {"563360.SH": "ETF"},
        lambda code, start, end: queried.append(code) or pd.DataFrame(),
        lambda code, start, end: queried.append(code) or pd.DataFrame(),
    )
    assert resolve_etf_code("563360", adapter.code_table) == "563360.SH"
    adapter.fetch_bars("563360", date(2024, 1, 2), date(2024, 1, 3))
    adapter.fetch_factors("563360", date(2024, 1, 2), date(2024, 1, 3))
    assert queried == ["563360.SH", "563360.SH"]


def test_cache_requires_coverage_and_refresh_is_explicit(tmp_path):
    provider = FakeProvider()
    service = MarketDataService(provider, tmp_path)
    with pytest.raises(FileNotFoundError):
        service.load("563360", date(2024, 1, 2), date(2024, 1, 3))
    assert provider.market_calls == 0

    data = service.load(
        "563360", date(2024, 1, 2), date(2024, 1, 3), refresh=True
    )
    assert provider.market_calls == 1
    assert data.index.name == "Date"
    assert list(data.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert data.loc["2024-01-02", "Close"] == 5.5
    assert data.loc["2024-01-02", "Volume"] == 100

    service.load("563360", date(2024, 1, 2), date(2024, 1, 3))
    assert provider.market_calls == 1
    with pytest.raises(ValueError, match="cover"):
        service.load("563360", date(2024, 1, 1), date(2024, 1, 3))


def test_adjustment_rejects_missing_and_misaligned_factors():
    bars = pd.DataFrame(
        {"Open": [2], "High": [4], "Low": [1], "Close": [3], "Volume": [5]},
        index=pd.to_datetime(["2024-01-02"]),
    )
    factors = pd.Series([1.0], index=pd.to_datetime(["2024-01-03"]))
    with pytest.raises(ValueError, match="match"):
        adjust_ohlc(bars, factors)
    with pytest.raises(ValueError, match="positive"):
        adjust_ohlc(bars, pd.Series([0.0], index=bars.index))
