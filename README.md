# Ploymarket BTC Simulator

一个只读、模拟盘优先的 BTC 预测市场研究工具。当前版本不会下实盘订单，也不需要钱包、私钥或 Polymarket API key。

## 当前能力

- 从 Polymarket Gamma API 发现活跃的 BTC / Bitcoin 相关市场。
- 用 CLOB 公开价格历史生成简单的 YES 动量信号，并区分 gross edge / net edge。
- 用统一风控规则做模拟开仓、止损、止盈和回测，并优先使用市场级真实 fee rate。
- 输出包含费用、滑点和 PnL 的回测交易 CSV，并生成逐市场、按类型聚合和组合级资金曲线 CSV。
- 生成逐 bar mark-to-market 组合曲线，用价格历史观察持仓期间回撤。
- 生成模拟订单状态机 CSV，为未来持续模拟盘和实盘订单生命周期做准备。
- `paper-run` 已区分 `TAKER`、`MAKER`、`SKIP` 执行计划，并优先使用本地 SQLite 历史数据避免网络慢请求拖死扫描。
- `spread-scan` 会读取 YES/NO 真实订单簿，检查完整组合价差机会，输出 `data/spread_scan.csv`。
- 可抓取 Coinbase 公开 BTC-USD 现货 K 线，作为后续外部价格锚点。

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
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml replay-backtest
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml paper-run
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml paper-loop --iterations 3 --interval-seconds 300
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml paper-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml spread-scan --market-type price_target
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml explain-risk
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml cache-info
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml storage-info
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml data-quality
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml btc-price
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml alignment-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml edge-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml daily-report
```

一键跑完整研究流水线：

```bash
scripts/research_cycle.sh
```

它会依次执行 BTC 价格更新、backtest、paper-run、paper-report、spread-scan、alignment、edge、strategy-sweep、data-quality 和 daily-report。

在 macOS 上定时运行，默认每 30 分钟执行一次：

```bash
scripts/install_research_cycle_launchd.sh
```

改成每 15 分钟：

```bash
scripts/install_research_cycle_launchd.sh 900
```

停止定时任务：

```bash
scripts/uninstall_research_cycle_launchd.sh
```

日志写入 `logs/`，该目录不会提交到 Git。

`paper-run` 输出里的 `execution_mode` 含义：

- `TAKER`: 净 edge 扣除 taker fee、滑点、安全边际后仍过线，可以作为模拟吃单候选。
- `MAKER`: gross edge 为正，但 taker 成本后不过线，只能作为更低限价的挂单候选。默认关闭，需在 `[execution]` 中显式启用后研究。
- `SKIP`: 不满足交易条件，继续观察。

可以用 `--market-type` 只观察某一类市场：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml discover --market-type price_target
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml signals --market-type company_treasury
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml backtest --market-type price_target
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml replay-backtest --market-type price_target
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
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml data-quality
```

SQLite 文件不会提交到 GitHub，用于本地长期研究样本积累。

离线回放只使用 SQLite 本地数据，不依赖实时 API：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml replay-backtest --market-type price_target
```

## 外部 BTC 价格

当前外部 BTC 价格源使用 Coinbase 公开 market candles：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml btc-price
```

输出：

```text
data/btc_price_candles.csv
```

这个数据源目前只用于研究，不直接触发交易。

## 样本验证

`paper-run` 会把每轮信号写入 SQLite 的 `paper_snapshots` 表。`alignment-report` 会把本地 Polymarket YES 价格历史与 BTC-USD K 线对齐，输出：

```text
data/alignment_report.csv
data/alignment_summary.csv
```

当前默认统计未来 `1h`、`3h`、`6h` 的 YES 价格变化和 BTC 收益率，用来判断信号是否真的有可重复 edge。

`edge-report` 会进一步按可提前知道的条件分层，例如 YES 价格区间和过去 1 小时 BTC 动量。注意：它不会用未来 BTC 收益做分组，避免引入未来函数。

当前默认启用了一个保守 BTC 过滤器：当 `YES >= 0.50` 且 BTC 过去 1 小时跌幅超过 `0.25%` 时，不允许做多 YES。这个规则来自 `edge-report` 的坏条件分层，不是盈利保证。

`daily-report` 会汇总当前模拟盘、回放、对齐和 edge 报告，并给出 `not_ready` / `candidate` 状态。

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
