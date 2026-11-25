# 快速开始

这份文档带你安装项目、运行第一次回测，并使用本地缓存再次运行。更完整的参数说明、策略规则、成本和结果解释见[完整使用指南](user-guide.md)。

## 准备环境

项目使用 Python 3.14 和 `uv`。在仓库根目录运行：

```sh
uv sync
```

仓库使用 `wheels/` 中的本地 wheel；不要在安装前删除该目录。

## 首次运行：刷新行情

刷新行情需要 AmazingData 本机环境、账号和行情权限。在仓库根目录创建 `.env`，填入本机凭据：

```dotenv
AD_USERNAME=你的用户名
AD_PASSWORD=你的密码
AD_HOST=你的服务主机
AD_PORT=你的服务端口
```

不要分享或提交真实凭据。然后执行刷新和回测：

```sh
uv run --env-file .env etf-swing \
  --symbol 563360 \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --refresh
```

替换 ETF 代码与日期区间。日期格式为 `YYYY-MM-DD`，起始日期不能晚于结束日期。`--refresh` 会获取行情、复权因子和交易日历，并将数据缓存到 `data/cache/`。

## 使用已有缓存

目标标的和日期都已被缓存覆盖时，无需 `.env` 或 `--refresh`：

```sh
uv run etf-swing \
  --symbol 563360 \
  --start 2024-01-01 \
  --end 2025-12-31
```

普通运行只读本地缓存，不会联网或补齐缺失数据。缓存不存在、不完整或未覆盖所选日期时，命令会报错；检查标的和日期，必要时重新显式刷新。

默认结果写入 `results/`：`result.json` 保存运行参数和汇总指标，`equity.csv` 保存权益曲线，`trades.csv` 保存交易记录。缓存与结果都是本机数据，不要提交到 Git。
