# ETF 波段量化

面向 ETF 策略研究的单标的日线回测工程骨架：读取行情、做前复权、运行回测，并导出可复查的结果。

> 当前策略是用于验证数据与回测流程的 SMA(20/60) 示例，不是已经验证有效的波段策略，也不构成投资建议。项目不支持多 ETF 组合、实盘下单、券商连接或信号推送。

## 文档

- [快速开始](docs/quickstart.md)：安装项目并完成首次回测。
- [完整使用指南](docs/user-guide.md)：详解运行步骤、参数、策略、成本和结果。

## Git 提交检查

启用仓库自带的提交前检查：

```sh
git config core.hooksPath .githooks
```

提交前会格式化 Python、YAML、TOML、JSON 和 Markdown 文件，再运行 Ruff lint 与 pytest；需要先安装依赖（`uv sync` 和 `bun install`）。
