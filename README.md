# ETF 波段量化

## 单标的日线回测

首次运行需在本机 `.env` 设置 `AMAZINGDATA_USERNAME`、`AMAZINGDATA_PASSWORD`、
`AMAZINGDATA_HOST` 和 `AMAZINGDATA_PORT`，然后显式刷新以获取缓存：

```sh
uv run --env-file .env etf-swing --start 2024-01-01 --end 2025-12-31 --refresh
```

默认标的是 `563360`，可用 `--symbol` 指定另一只 ETF；`--start` 和 `--end`
使用 `YYYY-MM-DD` 日期。行情 CSV 与复权因子 CSV 保存在 `data/cache/`。普通
运行只读取本地缓存，不查询行情或因子；若缓存缺失或交易日不完整会失败。
注意 CLI 在检查缓存前仍会登录 AmazingData。仅传入 `--refresh` 才在登录后
查询行情并获取因子（SDK 可使用本地因子缓存），随后更新项目 CSV 缓存。输出保存在
`results/`，包含 `result.json`、`equity.csv` 和 `trades.csv`。可用 `--output-dir`
和 `--cache-dir` 指定目录。

回测采用 SMA(20/60) 长仓/空仓示例、人民币 100,000 元初始资金、单边
0.00005 佣金率（每笔成交最低 0.1 元）和默认 `--spread 0.0005`。spread 是
回测框架的固定成本假设，不是实测点差或单边滑点。一次运行只处理一个 ETF。
SMA 示例用于验证工程管线，不代表最终策略或投资有效性结论，也不构成投资建议。
