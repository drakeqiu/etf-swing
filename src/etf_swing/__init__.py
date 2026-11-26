"""命令行单 ETF 回测入口。"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .backtest import (
    COMMISSION_RATE,
    DEFAULT_SPREAD,
    FAST_SMA_PERIOD,
    INITIAL_CASH,
    MIN_COMMISSION,
    SLOW_SMA_PERIOD,
    run_backtest,
)
from .market_data import (
    AmazingDataProvider,
    MarketDataProvider,
    MarketDataService,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="单 ETF 日线 SMA 回测")
    parser.add_argument("--symbol", default="563360")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    return parser


def _artifacts(
    stats: Any, symbol: str, start: date, end: date, spread: float
) -> dict[str, object]:
    trades = stats["_trades"]
    equity = stats["_equity_curve"]
    closed = trades[trades["ExitBar"] >= 0]
    hold = (
        float((closed["ExitBar"] - closed["EntryBar"]).mean())
        if not closed.empty
        else None
    )
    gains = closed.loc[closed["PnL"] > 0, "PnL"].sum()
    losses = -closed.loc[closed["PnL"] < 0, "PnL"].sum()
    profit_factor = float(gains / losses) if losses else None
    metrics = {
        "total_return": float(stats["Return [%]"]) / 100,
        "profit_factor": float(profit_factor)
        if profit_factor is not None
        else None,
        "max_drawdown": float(stats["Max. Drawdown [%]"]) / 100,
        "trade_count": int(len(closed)),
        "mean_holding_period": hold,
        "mean_holding_period_unit": "trading_day_bars",
    }
    return {
        "symbol": symbol,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "strategy": {
            "name": "SMA crossover",
            "fast_period": FAST_SMA_PERIOD,
            "slow_period": SLOW_SMA_PERIOD,
        },
        "initial_cash": INITIAL_CASH,
        "cost_assumptions": {
            "commission_rate_per_side": COMMISSION_RATE,
            "minimum_commission_per_fill": MIN_COMMISSION,
            "spread": spread,
            "spread_description": "框架固定假设，非实测点差或单边滑点",
        },
        "metrics": metrics,
        "_equity": equity,
        "_trades": trades,
    }


def run_cli(
    args: argparse.Namespace, provider: MarketDataProvider
) -> dict[str, object]:
    """通过注入数据提供器运行，不初始化 SDK。"""
    data = MarketDataService(provider, args.cache_dir).load(
        args.symbol, args.start, args.end, refresh=args.refresh
    )
    stats = run_backtest(data, spread=args.spread)
    result = _artifacts(stats, args.symbol, args.start, args.end, args.spread)
    result.update(data.attrs)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result["_equity"].to_csv(args.output_dir / "equity.csv")
    result["_trades"].to_csv(args.output_dir / "trades.csv", index=False)
    public = {
        key: value for key, value in result.items() if not key.startswith("_")
    }
    (args.output_dir / "result.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return public


def main(
    args: list[str] | None = None,
    provider: MarketDataProvider | None = None,
) -> None:
    """运行缓存回测，或在显式刷新时于命令边界认证 SDK。"""
    parsed = _parser().parse_args(args)
    if parsed.start > parsed.end:
        raise SystemExit("--start must not be after --end")
    if provider is not None:
        run_cli(parsed, provider)
        return
    if not parsed.refresh:

        class CacheOnlyProvider:
            def fetch_bars(self, symbol: str, start: date, end: date) -> Any:
                raise AssertionError("cache-only access must not fetch bars")

            def fetch_factors(
                self, symbol: str, start: date, end: date
            ) -> Any:
                raise AssertionError(
                    "cache-only access must not fetch factors"
                )

            def trading_sessions(self, start: date, end: date) -> Any:
                raise AssertionError(
                    "cache-only access must not query calendar"
                )

        run_cli(parsed, CacheOnlyProvider())
        return
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    from AmazingData import BaseData, MarketData, login, logout
    from AmazingData.query_api.market_data import Period

    username = os.environ["AD_USERNAME"]
    password = os.environ["AD_PASSWORD"]
    host = os.environ["AD_HOST"]
    port = int(os.environ["AD_PORT"])
    login(username, password, host, port)
    try:
        base_data = BaseData()
        calendar = base_data.get_calendar()
        market_data = MarketData(calendar)
        sdk_provider = AmazingDataProvider.from_sdk(
            base_data, market_data, period=Period.day.value, calendar=calendar
        )
        run_cli(parsed, sdk_provider)
    finally:
        logout(username)
