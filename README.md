# ETF 波段量化

面向 ETF 策略研究的单标的日线回测工程骨架：读取行情、做前复权、运行回测，并导出可复查的结果。

> 当前策略是用于验证数据与回测流程的 SMA(20/60) 示例，不是已经验证有效的波段策略，也不构成投资建议。项目不支持多 ETF 组合、实盘下单、券商连接或信号推送。

## 文档

- [快速开始](docs/quickstart.md)：安装项目并完成首次回测。
- [完整使用指南](docs/user-guide.md)：详解运行步骤、参数、策略、成本和结果。

## Git 提交规范

在仓库根目录启用提交检查和提交模板：

```sh
git config core.hooksPath .githooks
git config commit.template "$(git rev-parse --show-toplevel)/.gitmessage"
```

提交消息首行使用 `type(scope): subject`，`scope` 可省略。提交钩子校验格式；模板列出允许的类型和示例。提交前仍会格式化暂存文件，再运行 Ruff lint 与 pytest。依赖安装：`uv sync`、`bun install`。
