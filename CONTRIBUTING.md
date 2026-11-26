# 贡献指南

感谢参与项目改进。本项目用于单只 ETF 的历史回测；SMA(20/60) 只是验证数据与回测流程的示例策略，不代表已验证的投资策略。

## 开发环境

项目使用 Python 3.14 和 `uv`。在仓库根目录安装依赖：

```sh
uv sync
```

项目依赖包含 `wheels/` 中的本地 wheel，安装前不要删除该目录。修改 JSON 文件或运行对应格式检查时，还需要安装 Bun 依赖：

```sh
bun install --frozen-lockfile
```

## 开发流程

- 在独立分支上提交聚焦的改动。
- 行为变更应补充或更新对应测试；文档变更应同步更新相关说明。
- 测试应使用合成数据或假数据提供器，不依赖 AmazingData 凭据、网络或真实行情服务。
- 不要提交 `.env`、凭据、行情缓存、回测结果等本机数据。

## 本地检查

提交前运行与 CI 对应的核心检查：

```sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run mypy
uv run pytest
```

Markdown 可单独检查：

```sh
uv run mdformat --check README.md CONTRIBUTING.md
```

仓库 CI 还会检查 Markdown、JSON、YAML、TOML 格式以及 `.github/` 下的 YAML。

## 提交与 Pull Request

在仓库根目录启用提交钩子和提交模板：

```sh
git config core.hooksPath .githooks
git config commit.template "$(git rev-parse --show-toplevel)/.gitmessage"
```

提交说明首行使用 `type(scope): subject`，`scope` 可省略；可用类型和示例见 `.gitmessage`。提交钩子会检查格式，提交前钩子会格式化暂存文件并运行 Ruff lint 与 pytest。

Pull Request 请说明改动目的、行为影响和已运行的检查。若改动涉及输出、缓存或使用方式，也请附上相应文档更新。
