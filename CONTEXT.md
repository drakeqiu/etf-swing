# ETF 波段回测上下文

## 项目目标与边界

本项目是单只场内 ETF 的日线研究回测骨架：从行情获取与本地缓存开始，完成前复权、示例策略回测，并导出可复查结果。SMA(20/60) 只用于验证管线，不代表已确认有效的投资策略，也不构成投资建议。

当前不支持多标的组合与资金分配、券商连接、实盘下单或信号推送。核心领域用语以 [`GLOSSARY.md`](GLOSSARY.md) 为准；单标的管线与数据语义的决策见 [ADR-0001](docs/adr/0001-single-symbol-backtest-pipeline.md)。

## 架构与数据流

```text
CLI (src/etf_swing/__init__.py)
  ├─ 普通运行 → CacheOnlyProvider → 本地行情 CSV
  └─ 显式 --refresh → AmazingDataProvider → SDK 行情/因子/日历
                                  ↓
                    MarketDataService (market_data.py)
                    代码解析、日期规范化、严格前复权、缓存
                                  ↓
                    run_backtest (backtest.py)
                    SMA(20/60) 长仓/空仓、佣金与 spread
                                  ↓
                    result.json + equity.csv + trades.csv
```

- `MarketDataProvider` 是数据源边界；`AmazingDataProvider` 适配 SDK，`MarketDataService` 负责缓存和回测输入数据。SDK 登录、网络查询只在显式刷新的 CLI 边界发生。
- `run_cli` 通过注入 provider 编排回测与结果导出；测试用假 provider 和合成数据，不依赖凭据或网络。
- 回测输入为单个 ETF 的 `DatetimeIndex` 与 `Open`、`High`、`Low`、`Close`、`Volume`。默认标的是 `563360`，代码映射由 SDK 的 `EXTRA_ETF` 代码表解析。

## 领域不变量

- 普通运行只读缓存；请求区间未被缓存完整覆盖时明确失败。只有显式刷新才获取行情并更新本地数据。
- 前复权比例为“当日后复权因子 / 请求区间最新后复权因子”，同比例调整 OHLC，Volume 不变。行情和因子日期必须严格匹配；缺失、重复或错位数据显式失败，不填充、不回退未复权价格。
- 示例策略只做多或空仓：收盘形成的信号在下一根日线执行；初始资金 100,000 元，下单数量按 100 份取整，佣金按成交双边计提且每笔最低 0.1 元。默认 `spread=0.0005` 是框架成本假设，不是实测点差或滑点。
- 结果来自同一次回测：JSON 保存汇总指标与运行参数，CSV 保存权益曲线和交易记录；无亏损交易时 Profit Factor 为 `null`，平均持仓周期只统计已平仓交易并以交易日 bar 数表达。

## 修改时的边界

- 数据源、缓存或复权改动应保持 SDK 与核心数据变换隔离，并覆盖完整缓存命中、覆盖不足、显式刷新和日期对齐行为。
- 策略或成本改动应保留无前视偏差、佣金及 spread 语义，并检查导出参数和用户文档的一致性。
- CLI / 导出行为改动要一起检查 `tests/test_cli.py` 与用户指南；数据管线改动检查 `tests/test_market_data.py`；策略改动检查 `tests/test_backtest.py`。
- 本地行情缓存、结果文件、`.env` 和凭据不属于版本控制内容。开发环境、检查命令与 PR 流程见 [`CONTRIBUTING.md`](CONTRIBUTING.md)；使用方法见 [`docs/user-guide.md`](docs/user-guide.md)。
