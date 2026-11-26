from __future__ import annotations

import json
import math
from datetime import date

import pandas as pd
from synthetic_data import synthetic_data

from etf_swing import _parser, main


class SyntheticProvider:
    def __init__(self) -> None:
        self.bars = synthetic_data()

    def fetch_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        return self.bars

    def fetch_factors(
        self, symbol: str, start: date, end: date
    ) -> pd.DataFrame:
        return pd.DataFrame({"Factor": 1.0}, index=self.bars.index)

    def trading_sessions(self, start: date, end: date) -> pd.DatetimeIndex:
        sessions = self.bars.index
        return pd.DatetimeIndex(
            sessions[
                sessions.slice_indexer(
                    pd.Timestamp(start), pd.Timestamp(end)
                )
            ]
        )


def test_cli_exports_consistent_offline_run(tmp_path, monkeypatch) -> None:
    args = [
        "--start",
        "2025-01-01",
        "--end",
        "2025-09-30",
        "--refresh",
        "--spread",
        "0",
        "--cache-dir",
        str(tmp_path / "cache"),
        "--output-dir",
        str(tmp_path / "results"),
    ]
    main(args=args, provider=SyntheticProvider())

    saved = json.loads((tmp_path / "results/result.json").read_text())
    equity = pd.read_csv(tmp_path / "results/equity.csv")
    trades = pd.read_csv(tmp_path / "results/trades.csv")
    assert saved["symbol"] == "563360"
    assert saved["initial_cash"] == 100_000
    assert saved["strategy"]["fast_period"] == 20
    assert saved["strategy"]["slow_period"] == 60
    assert "total_return" in saved["metrics"]
    assert saved["metrics"]["max_drawdown"] <= 0
    assert saved["cost_assumptions"]["commission_rate_per_side"] == 0.00005
    assert saved["cost_assumptions"]["minimum_commission_per_fill"] == 0.1
    assert saved["metrics"]["trade_count"] >= 1
    assert saved["metrics"]["mean_holding_period_unit"] == "trading_day_bars"
    assert saved["metrics"]["mean_holding_period"] is not None
    assert math.isclose(
        saved["metrics"]["total_return"],
        float(equity["Equity"].iloc[-1]) / 100_000 - 1,
    )
    assert len(trades) == saved["metrics"]["trade_count"]

    assert saved["metrics"]["profit_factor"] is None
    assert not equity.empty
    assert saved["cost_assumptions"]["spread"] == 0

    for name in (
        "AD_USERNAME",
        "AD_PASSWORD",
        "AD_HOST",
        "AD_PORT",
    ):
        monkeypatch.delenv(name, raising=False)
    main(
        args=[
            "--start",
            "2025-01-01",
            "--end",
            "2025-09-30",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output-dir",
            str(tmp_path / "results"),
        ]
    )
    cached = json.loads((tmp_path / "results/result.json").read_text())
    assert cached["cache_status"] == "hit"


def test_cli_default_spread_and_cache_metadata(tmp_path) -> None:
    assert _parser().get_default("spread") == 0.0005
    main(
        args=[
            "--start",
            "2025-01-01",
            "--end",
            "2025-09-30",
            "--refresh",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output-dir",
            str(tmp_path / "results"),
        ],
        provider=SyntheticProvider(),
    )
    result = json.loads((tmp_path / "results/result.json").read_text())
    assert result["cost_assumptions"]["spread"] == 0.0005
    assert result["data_coverage_start"] == "2025-01-01"
    assert result["data_coverage_end"] == "2025-09-30"
    assert result["adjustment_reference_date"] == "2025-09-30"
    assert result["cache_status"] == "refreshed"


def test_cli_exports_null_profit_factor_when_no_trade_loses(tmp_path) -> None:
    class RisingProvider(SyntheticProvider):
        def __init__(self):
            close = list(range(100, 500))
            self.bars = pd.DataFrame(
                {
                    "Open": close,
                    "High": close,
                    "Low": close,
                    "Close": close,
                    "Volume": 1000,
                },
                index=pd.bdate_range("2024-01-01", periods=len(close)),
            )

    main(
        args=[
            "--start",
            "2024-01-01",
            "--end",
            "2025-02-28",
            "--refresh",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output-dir",
            str(tmp_path / "results"),
        ],
        provider=RisingProvider(),
    )
    result = json.loads((tmp_path / "results/result.json").read_text())
    assert result["metrics"]["profit_factor"] is None
