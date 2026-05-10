# Ploymarket BTC Simulator

一个只读、模拟盘优先的 BTC 预测市场研究工具。当前版本不会下实盘订单，也不需要钱包、私钥或 Polymarket API key。

## 当前能力

- 从 Polymarket Gamma API 发现活跃的 BTC / Bitcoin 相关市场。
- 用 CLOB 公开价格历史生成简单的 YES 动量信号，并区分 gross edge / net edge。
- 用统一风控规则做模拟开仓、止损、止盈和回测，并优先使用市场级真实 fee rate。
- 输出包含费用、滑点和 PnL 的回测交易 CSV，并生成逐市场、按类型聚合和组合级资金曲线 CSV。
- 生成逐 bar mark-to-market 组合曲线，用价格历史观察持仓期间回撤。
- 生成模拟订单状态机 CSV，为未来持续模拟盘和实盘订单生命周期做准备。

## 学习和项目文档

持续学习、系统状态、风控笔记和模拟盘记录都放在 [docs/](docs/README.md)。

如果使用 Obsidian，可以把 [docs/](docs/00-home.md) 作为 vault 打开：

```text
/Users/pizza_yang/code/ploymarket/docs
```

下次重新打开项目时，建议先读：

- [Obsidian 主页](docs/00-home.md)
- [当前系统状态](docs/system/current-state.md)
- [学习进度记录](docs/learning/progress-log.md)
- [模拟盘运行手册](docs/runbooks/paper-trading.md)

## 快速开始

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml discover
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml signals
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml backtest
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml paper-run
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml paper-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml explain-risk
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml cache-info
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml storage-info
```

可以用 `--market-type` 只观察某一类市场：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml discover --market-type price_target
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml signals --market-type company_treasury
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml backtest --market-type price_target
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml paper-run --market-type price_target
```

当前仓库还没有安装成包，所以命令里先显式加 `PYTHONPATH=src`。

## 风控从这里开始

第一阶段不要追求参数“完美”，先让每个限制都有清楚含义：

- `starting_cash`: 模拟盘本金。
- `max_position_usdc`: 单笔最多亏得起多少本金。
- `max_market_exposure_usdc`: 同一个预测问题最多占用多少资金。
- `max_total_exposure_usdc`: 所有持仓总敞口上限。
- `daily_loss_limit_usdc`: 当天亏到这里就停止开新仓。
- `max_drawdown_pct`: 账户从高点回撤到这里就停止开新仓。
- `stop_loss_pct`: 单笔买入后亏到这个比例退出。
- `take_profit_pct`: 单笔买入后赚到这个比例退出。
- `max_spread`: 流动性太差时不交易。

## 本地缓存

公开 API 响应会缓存到 `.cache/http/`，默认 `15` 分钟有效。缓存目录不会提交到 Git。

查看缓存状态：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml cache-info
```

相关配置在 `config/default.toml` 的 `[cache]` 区块。

## 本地 SQLite 存储

市场快照和价格历史会写入本地 SQLite：

```text
data/ploymarket.sqlite
```

查看状态：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml storage-info
```

SQLite 文件不会提交到 GitHub，用于本地长期研究样本积累。

默认值偏保守，是为了先观察策略行为。等我们看过几轮模拟盘结果，再逐步回答：

- 单笔亏损你心理上能不能接受？
- 连续亏损几笔之后是否应该停机？
- 这个策略是否主要亏在方向判断、滑点，还是入场太晚？
- 哪些市场流动性差，应该直接排除？

## 官方接口依据

- Polymarket Gamma API: `https://gamma-api.polymarket.com`
- Polymarket CLOB API: `https://clob.polymarket.com`
- 市场发现用 `GET /markets`
- 价格历史用 `GET /prices-history`

这些接口是公开只读接口，本项目当前不会调用任何交易端点。
