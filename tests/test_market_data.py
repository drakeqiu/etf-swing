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
        self.factor_calls = getattr(self, "factor_calls", 0) + 1
        return pd.DataFrame(
            {"Date": ["2024-01-02", "2024-01-03"], "Factor": [2.0, 4.0]}
        )
    def trading_sessions(self, start, end):
        return pd.DatetimeIndex(["2024-01-02", "2024-01-03"])


def test_adjustment_scales_every_ohlc_field_and_preserves_volume():
    bars = pd.DataFrame(
        {"Open": [10.0, 11.0], "High": [12.0, 13.0], "Low": [9.0, 10.0],
         "Close": [11.0, 12.0], "Volume": [100, 200]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )
    adjusted = adjust_ohlc(bars, pd.Series([2.0, 4.0], index=bars.index))
    assert adjusted.loc["2024-01-02"].to_dict() == {
        "Open": 5.0, "High": 6.0, "Low": 4.5, "Close": 5.5, "Volume": 100
    }
    assert adjusted.loc["2024-01-03"].to_dict() == {
        "Open": 11.0, "High": 13.0, "Low": 10.0, "Close": 12.0, "Volume": 200
    }


def test_sdk_filters_exact_symbol_and_supports_vendor_timestamp_and_factor_api():
    class Base:
        def get_code_list(self, security_type):
            return pd.DataFrame({"name": ["ETF", "ETF"]}, index=["SH.563360", "SH.588000"])

        def get_backward_factor(self, codes, local_path=None, is_local=True):
            assert codes == ["SH.563360"]
            return pd.DataFrame({"SH.563360": [2.0]}, index=pd.to_datetime(["2024-01-02"]))

    class Market:
        def query_kline(self, codes, begin_date, end_date, period):
            return pd.DataFrame({
                "kline_time": ["2024-01-02"], "code": ["SH.563360"],
                "open": [10], "high": [12], "low": [9], "close": [11], "volume": [10],
            })

    provider = AmazingDataProvider.from_sdk(Base(), Market(), period=10008)
    bars = provider.fetch_bars("563360", date(2024, 1, 2), date(2024, 1, 2))
    factors = provider.fetch_factors("563360", date(2024, 1, 2), date(2024, 1, 2))
    assert list(bars.Close) == [11]
    assert list(factors.Factor) == [2]



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
def test_sdk_adapter_uses_extra_etf_queries_and_normalizes_results():
    class FakeBaseData:
        def get_code_list(self, security_type):
            assert security_type == "EXTRA_ETF"
            return pd.DataFrame({"name": ["ETF"]}, index=["SH.563360"])

        def get_backward_factor(self, codes, local_path=None, is_local=True):
            assert codes == ["SH.563360"]
            return pd.DataFrame(
                {"SH.563360": [2.0, 4.0]},
                index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
            )

        def get_calendar(self):
            return [20240102, 20240103]

    class FakeMarketData:
        def query_kline(self, codes, begin_date, end_date, period):
            assert codes == ["SH.563360"]
            assert (begin_date, end_date, period) == (20240102, 20240103, 10008)
            return pd.DataFrame({
                "kline_time": ["2024-01-02", "2024-01-02"],
                "code": ["SH.588000", "SH.563360"],
                "open": [20.0, 10.0], "high": [22.0, 12.0],
                "low": [19.0, 9.0], "close": [21.0, 11.0],
                "volume": [500, 100],
            })

    provider = AmazingDataProvider.from_sdk(
        FakeBaseData(), FakeMarketData(), period=10008
    )
    bars = provider.fetch_bars(
        "563360", date(2024, 1, 2), date(2024, 1, 3)
    )
    factors = provider.fetch_factors(
        "563360", date(2024, 1, 2), date(2024, 1, 3)
    )

    assert list(bars.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert bars["Close"].tolist() == [11.0]
    assert bars.index.name == "Date"
    assert factors.index.name == "Date"
    assert factors["Factor"].tolist() == [2.0, 4.0]
    assert provider.trading_sessions(
        date(2024, 1, 2), date(2024, 1, 3)
    ).tolist() == list(pd.to_datetime(["2024-01-02", "2024-01-03"]))


def test_resolves_etf_from_dataframe_index():
    table = pd.DataFrame({"name": ["ETF"]}, index=["SH.563360"])
    assert resolve_etf_code("563360", table) == "SH.563360"


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
    assert provider.factor_calls == 1
    assert service.last_metadata["cache_status"] == "hit"
    assert service.last_metadata["adjustment_reference_date"] == "2024-01-03"
    service.load("563360", date(2024, 1, 2), date(2024, 1, 7))
    bars_path = tmp_path / "563360.csv"
    cached = pd.read_csv(bars_path)
    cached = cached[cached.Date != "2024-01-03"]
    cached.to_csv(bars_path, index=False)
    with pytest.raises(ValueError, match="sessions"):
        service.load("563360", date(2024, 1, 2), date(2024, 1, 3))
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
