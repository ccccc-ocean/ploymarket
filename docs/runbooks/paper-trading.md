# 模拟盘运行手册

## 运行前检查

确认位于项目根目录：

```bash
pwd
```

应该是：

```text
/Users/pizza_yang/code/ploymarket
```

确认测试通过：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m unittest discover tests
```

查看本地缓存状态：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml cache-info
```

查看 SQLite 存储状态：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml storage-info
```

## 发现市场

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml discover
```

关注：

- 找到了多少 BTC 相关市场。
- `yes` 价格是否极端接近 0 或 1。
- `liq` 是否太低。
- 问题是否真的和 BTC 价格相关，还是只是公司、人物或其他间接事件。

只看某一类市场：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml discover --market-type price_target
```

可用类型：

- `price_target`
- `price_range_daily`
- `company_treasury`
- `indirect_event`
- `unknown`

## 查看当前信号

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml signals
```

建议学习时先过滤：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml signals --market-type price_target
```

信号含义：

- `BUY_YES`: 当前版本认为 YES 有正向动量。
- `HOLD`: 没有足够优势。
- `AVOID`: 当前版本认为 YES 动量转弱。

输出字段里：

- `gross_edge`: 只看历史价格动量得到的原始优势。
- `net_edge`: 扣除 Taker fee、滑点和安全边际后的净优势。

优先关注 `net_edge`。如果 `gross_edge` 是正数但 `net_edge` 是负数，说明这个机会大概率被交易成本吃掉了。

注意：`BUY_YES` 只是研究信号，不是实盘建议。

## 单轮模拟盘扫描

`paper-run` 会执行一轮模拟盘信号扫描，并输出 CSV：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml paper-run --market-type price_target
```

输出文件：

```text
data/paper_run_<timestamp>.csv
```

字段包括：

- 市场 ID 和市场类型。
- YES 当前价格。
- 市场级 taker fee rate。
- 信号动作。
- gross edge / net edge。
- 信号原因。

这个命令适合未来接定时任务，每隔固定时间跑一轮，形成持续模拟盘记录。

## 跑回测

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml backtest
```

只回测价格目标类市场：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml backtest --market-type price_target
```

输出文件在：

```text
data/backtest_<market_id>.csv
data/backtest_summary.csv
data/backtest_summary_by_type.csv
data/portfolio_curve.csv
data/portfolio_summary.csv
data/portfolio_mtm_curve.csv
data/portfolio_mtm_summary.csv
data/orders_<market_id>.csv
data/orders_all.csv
```

复盘时重点看：

- 买入是否发生在价格已经过高的时候。
- `fee` 和 `slippage` 是否明显吞掉收益。
- 止损是否太紧或太松。
- 止盈是否过早。
- 盈亏是否来自少数偶然交易。
- 是否有大量 `REJECTED`，说明风控参数可能过紧。

## 回测汇总

`backtest_summary.csv` 是逐市场汇总，适合看每个市场的交易质量。

重点字段：

- `market_type`: 市场分类。
- `taker_fee_rate`: 市场级 Taker fee rate；如果市场没有提供则可能为默认/回退值。
- `trade_count`: 该市场买入和退出总次数。
- `entry_count`: 买入次数。
- `exit_count`: 退出次数。
- `rejected_count`: 被风控拒绝的次数。
- `win_rate`: 退出交易胜率。
- `realized_pnl`: 已实现盈亏。
- `total_fees`: 估算手续费。
- `total_slippage`: 估算滑点。
- `best_trade_pnl` / `worst_trade_pnl`: 最好和最差单笔退出。

`backtest_summary_by_type.csv` 是按市场类型聚合，适合回答：

- 哪一类市场有交易？
- 哪一类市场贡献了盈亏？
- 哪一类市场成本最高？
- 价格目标市场和公司事件市场是否应该分开优化？

注意：系统会优先使用 Polymarket 市场对象里的 `feeSchedule.rate`，没有该字段时才回退到 `config/default.toml` 里的 `taker_fee_rate`。

## 组合级资金曲线

`portfolio_curve.csv` 会把所有市场里的交易事件按时间排序，模拟一个账户的现金、已投入资金、账户净值和回撤。

重点字段：

- `cash`: 当前现金。
- `invested`: 当前仍在持仓里的投入本金。
- `equity`: `cash + invested` 的保守净值。
- `peak_equity`: 历史最高净值。
- `drawdown`: 相对历史最高净值的回撤。

`portfolio_summary.csv` 是组合级摘要：

- `ending_equity`: 回测结束净值。
- `realized_pnl`: 组合级盈亏。
- `total_fees`: 总手续费。
- `total_slippage`: 总滑点。
- `max_drawdown`: 最大回撤。
- `event_count`: 交易事件数量。

注意：当前组合曲线使用“持仓按投入本金计值”的保守口径，费用和滑点会立即降低净值；它还不是逐 bar mark-to-market 的精细资金曲线。

`portfolio_mtm_curve.csv` 是逐 bar mark-to-market 组合曲线。它会在持仓期间用价格历史持续重估未平仓仓位。

`portfolio_mtm_summary.csv` 是逐 bar 重估后的组合摘要。

两者区别：

- `portfolio_curve.csv`: 只在交易事件时更新。
- `portfolio_mtm_curve.csv`: 在交易事件和价格历史点都更新，更适合观察持仓期间真实回撤。

## 订单状态机

`orders_<market_id>.csv` 和 `orders_all.csv` 记录模拟订单生命周期。

当前模拟成交路径：

```text
created -> submitted -> accepted -> matched -> settled
```

风控拒绝路径：

```text
created -> rejected
```

重点字段：

- `order_id`: 本地生成的模拟订单 ID。
- `side`: `buy_yes` 或 `sell_yes`。
- `status`: 当前订单状态。
- `price`: 模拟执行价格。
- `notional`: 模拟订单名义金额。
- `reason`: 触发订单或拒绝订单的原因。

这一步是为了未来实盘做准备。真实 Polymarket 下单不是“发出请求就等于最终成交”，所以我们从模拟盘阶段就开始记录订单生命周期。

## 查看风控配置说明

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml explain-risk
```

## 常见问题

### API 偶尔报 IncompleteRead 或 RemoteDisconnected

这是公共接口或网络连接不稳定导致的。当前代码已经做了重试、单市场跳过和本地缓存。

缓存行为：

- 成功的 GET JSON 响应会写入 `.cache/http/`。
- 默认 `15` 分钟内重复请求会直接读缓存。
- 如果远程请求失败，且本地有旧缓存，会用旧缓存继续运行。
- `.cache/` 不提交到 GitHub。

### SQLite 存储

`discover`、`signals` 和 `backtest` 会把市场和价格历史写入：

```text
data/ploymarket.sqlite
```

当前存储内容：

- `markets`: 市场快照、分类、YES token、市场级 fee rate。
- `price_history`: YES token 历史价格点。

SQLite 文件用于本地长期学习，不提交到 GitHub。

### 找到的 BTC 市场太少或太杂

调整：

```toml
[universe]
keywords = ["bitcoin", "btc"]
min_liquidity = 1000.0
```

如果间接市场太多，后续需要加入更细的分类器，比如只保留包含 `price`, `above`, `below`, `reach`, `dip` 的市场。

### 回测盈利是否说明可以实盘

不能。当前回测还没有模拟真实盘口、成交概率、交易延迟、市场结算和 API 故障。它只能帮助我们筛掉明显不靠谱的想法。
