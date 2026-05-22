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
- `price_target_daily`
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
- `execution_mode`: `TAKER`、`MAKER` 或 `SKIP`。
- `limit_price`: 执行计划里的模拟限价。
- `expected_net_edge`: 对应执行方式下的预期净 edge。
- `execution_reason`: 为什么选择这种执行方式。

`paper-run` 是实时模拟扫描，不能把本地 SQLite 缓存当作可交易依据。现在它必须拿到 live 市场和 live 价格历史；如果实时发现或历史拉取失败，本轮会降级为 `data_degraded` / 空扫描，并在 `daily-report` 中保持 `not_ready`。

这个命令适合未来接定时任务，每隔固定时间跑一轮，形成持续模拟盘记录。

持续运行多轮：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml paper-loop --market-type price_target --interval-seconds 300 --iterations 0
```

参数说明：

- `--interval-seconds`: 每轮间隔秒数。
- `--iterations`: 运行轮数，`0` 表示一直运行直到手动停止。

也可以直接运行脚本：

```bash
scripts/paper_run_once.sh
scripts/paper_loop.sh
```

## 模拟盘复盘报告

`paper-report` 会聚合已有的 `paper_run_*.csv`：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml paper-report
```

输出文件：

```text
data/paper_report.csv
```

它会记录每一轮：

- 市场数量。
- `BUY_YES` / `HOLD` / `AVOID` 数量。
- `TAKER` / `MAKER` / `SKIP` 数量。
- 本轮最佳 net edge。
- 本轮最佳候选市场。

这个报告用于观察信号是否持续出现，而不是只看单轮偶然结果。

## YES/NO 双边价差扫描

`spread-scan` 会读取真实 CLOB 订单簿里的 YES/NO 最佳 bid/ask，检查完整组合价差：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml spread-scan --market-type price_target
```

输出文件：

```text
data/spread_scan.csv
```

重点看：

- `BUY_BOTH`: 如果 `YES ask + NO ask + 费用 + 滑点 < 1`，理论上可同时买入 YES/NO 完整组合，等待 merge/redeem。
- `SELL_BOTH`: 如果已经持有完整组合，且 `YES bid + NO bid - 费用 - 滑点 > 1`，理论上可双边卖出。
- `buy_pair_edge` / `sell_pair_edge`: 扣除估算费用和滑点后的净优势。
- 当前这个命令只做只读扫描，不会下单；只有连续多轮出现正 edge、且订单簿深度足够时，才考虑进入模拟盘成交状态机。

## 跑回测

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml backtest
```

只回测价格目标类市场：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml backtest --market-type price_target
```

## 离线回放

`replay-backtest` 只使用 SQLite 本地保存的市场和价格历史，不访问实时 API：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml replay-backtest --market-type price_target
```

这适合做可重复实验。若同一份 SQLite 数据不变，回放结果也应该保持一致。

本轮本地样本观察：

- 市场数：35。
- 有交易市场：4。
- 交易数：14。
- 组合 PnL：约 `+10.25 USDC`。
- 逐 bar mark-to-market 最大回撤：约 `1.8%`。

这个结果只能说明当前小样本回放为正，不能说明已经可以实盘。

## 数据质量

查看本地样本覆盖：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml data-quality
```

输出文件：

```text
data/data_quality.csv
```

优先关注：

- `with_history`: 有价格历史的市场数量。
- `with_24plus_points`: 至少有 24 个价格点的市场数量。
- `price_points`: 总价格点数。

## 市场类型对比

按市场类型分别回测本地样本：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml market-type-report
```

输出：

```text
data/market_type_report.csv
```

重点看：

- 哪类市场实际触发了交易。
- 哪类市场 PnL 为正或接近正。
- 哪类市场只是样本多，但旧策略完全不交易。

当前用途：把 `price_target_daily` 这类短周期 BTC 市场从长期目标市场中拆出来，后续单独设计边界/临近结算策略。

## Maker 研究开关

默认配置里 `maker_enabled = false`。原因是当前本地小样本显示：如果把 Maker 候选纳入“触价成交 + TTL 取消”的模拟，回测结果会从小幅盈利变成明显亏损。

如果要研究 Maker，可以临时把 `config/default.toml` 的 `[execution]` 改为：

```toml
maker_enabled = true
```

开启后重点检查：

- `orders_all.csv` 里有多少 `canceled`。
- `MAKER_BUY_YES` 是否常常成交后继续下跌。
- Maker 改善的价格是否足以弥补逆向选择风险。

## 外部 BTC 现货价格

抓取 Coinbase 公开 BTC-USD K 线：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml btc-price
```

输出文件：

```text
data/btc_price_candles.csv
```

本数据源目前只用于研究。下一步可以用它比较：

- BTC 现货价格变化。
- Polymarket YES 价格变化。
- 是否存在预测市场价格滞后或过度反应。

## BTC/Polymarket 时间对齐

生成对齐报告：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml alignment-report --market-type price_target
```

输出：

```text
data/alignment_report.csv
data/alignment_summary.csv
```

当前统计：

- `1h`: 未来 1 小时 YES 价格变化和 BTC 收益率。
- `3h`: 未来 3 小时 YES 价格变化和 BTC 收益率。
- `6h`: 未来 6 小时 YES 价格变化和 BTC 收益率。
- 底层采样已切到 5 分钟粒度：Polymarket `prices-history` 使用 `fidelity=5`，Coinbase BTC-USD 使用 `FIVE_MINUTE`。
- 信号窗口仍保持近似原来的时间长度：短窗 `72` 个 5 分钟点约等于 6 小时，长窗 `288` 个 5 分钟点约等于 24 小时。

## 策略参数扫描

每轮流水线会额外运行一组保守的 5 分钟参数候选：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml strategy-sweep --market-type price_target --limit 10
```

输出：

```text
data/strategy_sweep.csv
```

它的用途是持续观察哪些参数组合在当前样本里更接近盈利，而不是自动把单轮最优参数写回默认配置。只有当同一类参数在多轮、多市场、足够交易数下持续优于默认策略，才考虑升级为默认策略。

本轮样本：

- `1h`: 5377 条，平均 YES 变化约 `-0.0005`，平均 BTC 收益约 `0.0321%`。
- `3h`: 5307 条，平均 YES 变化约 `-0.0011`，平均 BTC 收益约 `0.0605%`。
- `6h`: 5202 条，平均 YES 变化约 `-0.0021`，平均 BTC 收益约 `0.0986%`。

这不是交易信号，只是基础统计。后续需要按 `BUY_YES`、`HOLD`、市场流动性、到期时间和 BTC 涨跌区间分层。

## Edge 分层报告

生成分层 edge 报告：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml edge-report --min-samples 30
```

输出：

```text
data/edge_report.csv
```

当前第一版分组条件：

- `horizon_hours`: 未来观察窗口。
- `yes_price_bucket`: 当前 YES 价格区间。
- `btc_past_1h_bucket`: 过去 1 小时 BTC 收益区间。

重点：分组条件只使用当时已经知道的信息。未来 BTC 收益只作为结果字段保留，不能作为实盘条件。

本轮观察：

- 最好桶：`1h / YES 0.20-0.50 / BTC过去1h下跌0.25%-1%`，平均 YES 变化约 `+0.0022`，样本 `99`。
- 最差桶：`6h / YES>=0.50 / BTC过去1h下跌0.25%-1%`，平均 YES 变化约 `-0.0414`，样本 `33`。

当前更强的结论是排除坏条件，而不是直接开仓：高 YES 价格市场在 BTC 短线走弱后风险明显更差。

## BTC 动量过滤器

默认配置：

```toml
[btc_filter]
enabled = true
lookback_hours = 1
down_threshold = -0.0025
avoid_yes_price_gte = 0.50
```

含义：如果 YES 价格已经不低，同时 BTC 过去 1 小时下跌超过 `0.25%`，系统不允许做多 YES。

本轮离线回放观察：

- 交易数：从 `14` 降到 `12`。
- 组合 PnL：从约 `+10.25 USDC` 提升到约 `+17.74 USDC`。
- 逐 bar mark-to-market 最大回撤：从约 `1.8%` 降到约 `1.2%`。

这仍然只是小样本结果，不能外推为稳定盈利。

## 每日复盘报告

生成日报：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml daily-report
```

输出：

```text
data/daily_report.csv
```

当前 readiness 规则偏保守：

- paper-run 样本至少需要多轮连续观察。
- 离线回放交易数需要足够多。
- alignment 样本需要足够大。
- 扣费后回放 PnL 需要为正。
- 最大回撤不能超过保守阈值。

当前状态：`not_ready`，主要原因是 paper-run 样本太少。

## 一键研究流水线

运行：

```bash
scripts/research_cycle.sh
```

它会按顺序执行：

- `btc-price`
- `backtest`
- `paper-run`
- `paper-report`
- `spread-scan`
- `flow-scan`
- `alignment-report`
- `edge-report`
- `strategy-sweep`
- `market-type-report`
- `data-quality`
- `daily-report`

这个脚本适合接入本地定时任务。当前运行后仍然是 `not_ready`，原因是长期 paper-run 样本不足。

## macOS 定时运行

推荐使用 `launchd`，它比手动开终端更适合长期后台运行。

默认每 30 分钟运行一次：

```bash
scripts/install_research_cycle_launchd.sh
```

指定间隔秒数，例如每 15 分钟：

```bash
scripts/install_research_cycle_launchd.sh 900
```

当前 5 分钟研究模式：

```bash
scripts/install_research_cycle_launchd.sh 300
```

检查是否已加载：

```bash
launchctl list | grep com.ploymarket.research-cycle
```

查看日志：

```bash
tail -f logs/research_cycle.out.log
tail -f logs/research_cycle.err.log
```

停止定时任务：

```bash
scripts/uninstall_research_cycle_launchd.sh
```

当前建议：5 分钟粒度研究可以用 `300` 秒，但必须依赖 `research_cycle.sh` 里的锁防止上一轮未结束时重叠运行。

## macOS 系统防睡眠设置

目标是系统层面设置“屏幕可以熄灭，但 Mac 不进入睡眠”，而不是依赖项目里的常驻脚本。

当前推荐设置：

```bash
sudo pmset -c sleep 0 disksleep 0 displaysleep 5
```

含义：

- `-c`: 只修改接电源时的设置。
- `sleep 0`: 接电源时系统不自动睡眠。
- `disksleep 0`: 接电源时磁盘不自动睡眠。
- `displaysleep 5`: 屏幕 5 分钟后熄灭，但系统仍保持运行。

检查当前设置：

```bash
pmset -g custom
```

重点看 `AC Power` 下：

- `sleep` 应为 `0`。
- `disksleep` 应为 `0`。
- `displaysleep` 可以是你希望的屏幕熄灭分钟数。

注意：不要合上 MacBook 盖子。合盖通常会触发更强的硬件睡眠策略，即使系统设置为不自动睡眠，也不保证脚本继续联网运行。

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
