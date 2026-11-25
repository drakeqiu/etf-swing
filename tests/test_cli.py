from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

from etf_swing import main


class SyntheticProvider:
    def __init__(self) -> None:
        close = np.array(
            [100.0] * 75 + list(np.linspace(101, 180, 45)) + [180.0] * 20
            + list(np.linspace(179, 70, 65))
        )
        self.bars = pd.DataFrame(
            {
                "Open": close,
                "High": close + 1,
                "Low": close - 1,
                "Close": close,
                "Volume": 1_000_000,
            },
            index=pd.date_range("2025-01-01", periods=len(close), freq="B"),
        )

    def fetch_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        return self.bars

    def fetch_factors(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            {"Factor": 1.0}, index=self.bars.index
        )


def test_cli_exports_consistent_offline_run(tmp_path) -> None:
    args = [
        "--start", "2025-01-01", "--end", "2025-09-30", "--refresh",
        "--spread", "0", "--cache-dir", str(tmp_path / "cache"),
        "--output-dir", str(tmp_path / "results"),
    ]
    main(args=args, provider=SyntheticProvider())

    saved = json.loads((tmp_path / "results/result.json").read_text())
    equity = pd.read_csv(tmp_path / "results/equity.csv")
    trades = pd.read_csv(tmp_path / "results/trades.csv")
    assert saved["symbol"] == "563360"
    assert saved["metrics"]["trade_count"] >= 1
    assert saved["metrics"]["mean_holding_period_unit"] == "trading_day_bars"
    assert len(trades) == saved["metrics"]["trade_count"]
    assert not equity.empty
    assert saved["cost_assumptions"]["spread"] == 0
