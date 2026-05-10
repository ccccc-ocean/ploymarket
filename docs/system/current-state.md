# 当前系统状态

最后更新：2026-05-07

## 项目定位

`ploymarket` 当前是一个 BTC 预测市场研究和模拟盘工具。它只读公开数据，不会下实盘订单，也不会读取钱包、私钥或交易 API key。

## 已实现功能

### 市场发现

代码位置：[src/ploymarket_sim/polymarket.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/polymarket.py)

- 搜索 BTC / Bitcoin 相关 Polymarket 市场。
- 过滤活跃、未关闭、有订单簿、达到最低流动性的市场。
- 提取市场问题、slug、流动性、24 小时成交量、YES 价格、CLOB token id。

### 本地缓存

代码位置：[src/ploymarket_sim/cache.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/cache.py)

- 缓存公开 GET JSON 响应。
- 默认目录：`.cache/http`
- 默认 TTL：`900` 秒。
- 远程请求失败时，如果存在旧缓存，可以使用 stale cache。
- 缓存目录已加入 `.gitignore`。

查看缓存：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml cache-info
```

### SQLite 存储

代码位置：[src/ploymarket_sim/storage.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/storage.py)

- 存储市场快照。
- 存储价格历史点。
- `discover`、`signals`、`backtest` 会自动写入。
- 默认路径：`data/ploymarket.sqlite`
- SQLite 文件已加入 `.gitignore`。

查看存储：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml storage-info
```

### 市场分类

代码位置：[src/ploymarket_sim/classifier.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/classifier.py)

- `price_target`: BTC 价格目标市场。
- `price_range_daily`: 日内或短周期价格范围市场。
- `company_treasury`: MicroStrategy / MSTR / 公司 BTC 持仓事件市场。
- `indirect_event`: 只和 BTC 间接相关的市场。
- `unknown`: 第一版规则无法判断的市场。

CLI 支持：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml discover --market-type price_target
```

### 价格历史

代码位置：[src/ploymarket_sim/clob.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/clob.py)

- 调用 CLOB `prices-history` 获取 YES token 的历史价格。
- 当前默认参数：
  - `interval = 1w`
  - `fidelity = 60` 分钟

### 信号生成

代码位置：[src/ploymarket_sim/signals.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/signals.py)

当前信号是简单均线动量：

- 计算短窗口均价和长窗口均价。
- 计算 `gross_edge` 和扣除 Taker fee、滑点、安全边际后的 `net_edge`。
- 如果短期均值明显高于长期均值，当前价格没有太接近 1，且 `net_edge` 达到门槛，生成 `BUY_YES`。
- 如果短期均值明显低于长期均值，生成 `AVOID`。
- 其他情况为 `HOLD`。

成本估算代码位置：[src/ploymarket_sim/costs.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/costs.py)

### 风控

代码位置：[src/ploymarket_sim/risk.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/risk.py)

当前风控规则包括：

- `max_position_usdc`: 单笔最大投入。
- `max_market_exposure_usdc`: 单个市场最大敞口。
- `max_total_exposure_usdc`: 总持仓敞口。
- `max_open_positions`: 最大同时持仓数。
- `daily_loss_limit_usdc`: 日内亏损上限。
- `max_drawdown_pct`: 最大账户回撤。
- `stop_loss_pct`: 单笔止损比例。
- `take_profit_pct`: 单笔止盈比例。
- `max_spread`: 最大允许价差。
- `min_price` / `max_price`: 不交易过于极端的价格。

### 回测

代码位置：[src/ploymarket_sim/backtest.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/backtest.py)

- 对每个市场逐步读取历史价格。
- 使用当前信号决定是否模拟买入 YES。
- 使用风控决定是否允许开仓。
- 使用止损、止盈和回测结束平仓退出。
- 输出每个市场一份 CSV，包含费用、滑点、净 edge 和 PnL。
- 输出逐市场汇总 CSV 和按市场类型聚合汇总 CSV。

当前费用模型：

```text
taker_fee = notional * taker_fee_rate * p * (1 - p)
```

fee rate 来源：

- 优先使用 Polymarket market 对象里的 `feeSchedule.rate`。
- 如果市场没有提供 fee schedule，则回退到 `config/default.toml` 的 `backtest.taker_fee_rate`。

汇总代码位置：[src/ploymarket_sim/summary.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/summary.py)

汇总输出：

- `data/backtest_summary.csv`
- `data/backtest_summary_by_type.csv`
- `data/portfolio_curve.csv`
- `data/portfolio_summary.csv`

### 组合级资金曲线

代码位置：[src/ploymarket_sim/portfolio.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/portfolio.py)

- 将多个市场的交易事件按时间排序。
- 模拟组合账户现金、已投入本金、净值、峰值净值和回撤。
- 使用保守口径：持仓按投入本金计值，费用和滑点立即降低净值。
- 输出组合级最大回撤和账户级 PnL。
- 输出逐 bar mark-to-market 资金曲线，用价格历史重估未平仓仓位。

输出：

- `data/portfolio_curve.csv`
- `data/portfolio_summary.csv`
- `data/portfolio_mtm_curve.csv`
- `data/portfolio_mtm_summary.csv`

### Paper Order 状态机

代码位置：[src/ploymarket_sim/orders.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/orders.py)

当前模拟成交路径：

```text
created -> submitted -> accepted -> matched -> settled
```

当前风控拒绝路径：

```text
created -> rejected
```

输出：

- `data/orders_<market_id>.csv`
- `data/orders_all.csv`

这个状态机目前只服务模拟盘，但字段设计为未来实盘订单生命周期预留空间。

### CLI

代码位置：[src/ploymarket_sim/cli.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/cli.py)

可用命令：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml discover
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml signals
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml backtest
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml paper-run
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml explain-risk
```

### Paper Run

代码位置：[src/ploymarket_sim/paper.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/paper.py)

- 执行一轮模拟盘信号扫描。
- 默认适合按 `price_target` 市场运行。
- 写入 SQLite 市场和价格历史。
- 输出 `data/paper_run_<timestamp>.csv`。

### Paper Report

代码位置：[src/ploymarket_sim/paper_report.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/paper_report.py)

- 聚合已有 `paper_run_*.csv`。
- 输出 `data/paper_report.csv`。
- 跟踪每轮信号数量、最佳 net edge 和最佳候选市场。

## 当前限制

- 没有真实订单执行。
- 有单轮 `paper-run`，但还没有守护进程或自动定时调度。
- 有本地 SQLite 存储，但还没有用于回放历史采样或离线回测。
- 没有盘口深度模拟。
- 没有考虑到期结算和市场 resolution 风险。
- 没有接 BTC 现货/永续价格源。
- 当前信号很初级，不能直接作为实盘依据。
- 当前费用模型已经读取市场级 fee rate，但仍然没有读取更复杂的 maker rebate、reward 和真实成交路径费用。
- 市场分类还是关键词规则，后续要用真实样本不断修正。
- 逐 bar mark-to-market 已实现，但仍基于当前 CLOB 历史价格，不包含盘口深度和成交概率。
- 订单状态机还没有真实的失败、撤单、部分成交和链上 settlement 查询。

## 知识库状态

`docs/` 现在同时承担两个角色：

- GitHub 文档目录。
- Obsidian vault。

Obsidian 入口是：[00-home.md](/Users/pizza_yang/code/ploymarket/docs/00-home.md)

## 重要原则

进入实盘之前，必须先满足：

- 模拟盘稳定运行至少数周。
- 每笔交易有可解释原因。
- 每次亏损都能归类。
- 风控能自动阻止继续扩大亏损。
- 真实小仓位测试的滑点和成交情况可接受。
