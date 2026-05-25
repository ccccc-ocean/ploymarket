# 当前系统状态

最后更新：2026-05-20

## 项目定位

`ploymarket` 当前是一个 BTC 预测市场研究和模拟盘工具。它只读公开数据，不会下实盘订单，也不会读取钱包、私钥或交易 API key。

## 已实现功能

### 市场发现

代码位置：[src/ploymarket_sim/polymarket.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/polymarket.py)

- 搜索 BTC / Bitcoin 相关 Polymarket 市场。
- 过滤活跃、未关闭、有订单簿、达到最低流动性的市场。
- 提取市场问题、slug、流动性、24 小时成交量、YES/NO 价格、YES/NO CLOB token id。

### 本地缓存

代码位置：[src/ploymarket_sim/cache.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/cache.py)

- 缓存公开 GET JSON 响应。
- 默认目录：`.cache/http`
- 默认 TTL：`900` 秒。
- 远程请求失败时，如果存在旧缓存，可以使用 stale cache。
- HTTP 请求增加运行级硬截止时间，避免外部 API 慢请求让模拟盘长期卡住。
- 缓存目录已加入 `.gitignore`。

查看缓存：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml cache-info
```

### SQLite 存储

代码位置：[src/ploymarket_sim/storage.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/storage.py)

- 存储市场快照。
- 存储价格历史点。
- 可以从 SQLite 读取已存市场和价格历史。
- `discover`、`signals`、`backtest` 会自动写入。
- `paper-run` 和 `spread-scan` 是实时扫描：必须使用 live 市场；VPS 严格实时配置的 `fresh_market_ttl_seconds=0`，live discovery 抖动时不生成新开仓依据。
- `paper-run` 的价格历史和 `spread-scan` 的订单簿仍必须实时拉取；历史缓存只用于离线研究和回测。
- `kalshi-discover` 是 Kalshi 只读公开市场发现，当前只抓 BTC 相关市场，不登录、不签名、不下单。
- `cross-platform-report` 会把 Polymarket/Kalshi BTC 市场按 strike、方向和日期归一化匹配，输出 `data/cross_platform_matches.csv`；当前是跨平台快照匹配，还不是 Kalshi 历史回测。
- `replay-backtest` 可以只使用 SQLite 本地数据离线回放。
- `data-quality` 输出本地市场和历史价格覆盖情况。
- `paper_snapshots` 保存每轮模拟盘信号和执行计划。
- `paper_positions` 保存实时模拟盘的同市场持仓状态；已有模拟持仓时不会每轮重复 TAKER，分批止盈会降低仓位，止盈后短冷却，止损后长冷却。
- `stale_tokens` 记录最近 CLOB 404 的 token，避免 `spread-scan` 反复扫描已失效订单簿。
- 默认路径：`data/ploymarket.sqlite`
- SQLite 文件已加入 `.gitignore`。

查看存储：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml storage-info
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml data-quality
```

### 市场分类

代码位置：[src/ploymarket_sim/classifier.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/classifier.py)

- `price_target`: BTC 价格目标市场。
- `price_target_daily`: 单日 BTC 价格目标市场，例如 “Will Bitcoin reach $84,000 on May 19?”。
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
- 调用 CLOB `book` 获取 YES/NO token 的当前最佳 bid/ask，用于双边价差扫描。
- 当前默认参数：
  - `interval = 1w`
  - `fidelity = 5` 分钟

### YES/NO 双边价差扫描

代码位置：[src/ploymarket_sim/spread_scan.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/spread_scan.py)

- 新增 `spread-scan` 命令，读取真实 CLOB 订单簿，而不是用 `1 - YES` 假设 NO 价格。
- 计算 `BUY_BOTH`: 同时买入 1 YES + 1 NO，若 `YES ask + NO ask + 费用 + 滑点 < 1`，理论上可等待 merge/redeem 获利。
- 计算 `SELL_BOTH`: 如果已经持有完整 YES/NO 组合，若 `YES bid + NO bid - 费用 - 滑点 > 1`，理论上可双边卖出获利。
- 输出 `data/spread_scan.csv`。
- 当前只做只读监控，不会下单。下一步需要连续观察正 edge 的持续性、可成交深度和机会消失速度，再进入模拟盘状态机。

### 外部 BTC 现货价格

代码位置：[src/ploymarket_sim/btc_price.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/btc_price.py)

- 使用 Coinbase 公开 BTC-USD candles。
- 当前默认粒度：`FIVE_MINUTE`。
- 输出 `data/btc_price_candles.csv`。
- 当前用于研究、回测对齐和 strike 距离诊断。
- 策略不能硬编码固定 strike，必须根据当前 BTC 现货动态判断 market strike 的相对位置。

### 资金流扫描

代码位置：[src/ploymarket_sim/flow_scan.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/flow_scan.py)

- 新增 `flow-scan` 命令。
- 使用 Polymarket Data API 按 `conditionId` 拉取最近交易流。
- 输出 `data/flow_scan.csv`。
- 统计 `BUY/SELL + YES/NO`、大额交易数、活跃钱包数、最大成交钱包和 YES/NO 净资金压力。
- 同时输出 `strike_direction`、`strike_distance_pct`、`strike_risk`，用于统一诊断 `above` 和 `under/below` 市场。
- 当前只作为观察和回测分层条件，不直接触发交易。

### BUY_NO 候选与反转回测

代码位置：[src/ploymarket_sim/reversal_backtest.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/reversal_backtest.py)

- 新增 `reversal-backtest` 命令。
- 对同一批 `price_range_daily` 历史并排比较：
  - `YES_ONLY_SL25`
  - `YES_NO_SL25`
  - `YES_NO_REV_SL25_CD60M`
  - `YES_NO_REV_SL15_CD60M`
  - `YES_NO_REV_SL12_CD60M`
- 输出 `data/reversal_summary.csv` 和 `data/reversal_trades.csv`。
- 第一轮实验显示：允许 `BUY_NO` 明显改善当前样本，但把止损收紧到 `12%/15%` 会产生更多噪音交易并恶化 PnL。
- 反转不是无脑反手，必须重新满足反向净 edge；否则会在 5 分钟市场里被来回扫损。
- `BUY_NO` 已从单独实验升级到主候选策略层：`signals`、`execution`、`backtest`、`portfolio`、`paper-run` 和 `paper-report` 都能识别 `BUY_NO`。
- 主候选策略只在 `price_range_daily` 市场允许 `BUY_NO`，并按 NO 价格自身做价格上下限过滤，避免把 1 cents 翻转玩法混进 BTC 主策略。
- 当前 `BUY_NO` 仍然只是模拟盘候选，不代表可以实盘。

### 时间对齐报告

代码位置：[src/ploymarket_sim/alignment.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/alignment.py)

- 将本地 Polymarket YES 历史价格与 BTC-USD K 线对齐。
- 默认计算未来 `1h`、`3h`、`6h` 的 YES 变化和 BTC 收益率。
- 底层 YES 价格历史和 BTC K 线已切换到 5 分钟粒度，便于后续扩展到 `5m`、`15m`、`30m` 短线市场研究。
- 输出：
  - `data/alignment_report.csv`
  - `data/alignment_summary.csv`

### Edge 分层报告

代码位置：[src/ploymarket_sim/edge_report.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/edge_report.py)

- 读取 `data/alignment_report.csv`。
- 按 `horizon_hours`、当前 YES 价格区间、过去 1 小时 BTC 动量分组。
- 输出 `data/edge_report.csv`。
- 分组条件只使用过去/当前信息，避免未来函数。

### 策略参数扫描

代码位置：[src/ploymarket_sim/strategy_sweep.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/strategy_sweep.py)

- 每轮在本地 5 分钟历史数据上测试一组保守候选参数。
- 输出 `data/strategy_sweep.csv`。
- 当前扫描维度包括短/长均线窗口、`min_momentum`、`min_edge` 和 BTC 下跌过滤阈值。
- 这个报告只用于研究，不会自动改写默认配置，避免因为单轮样本过拟合。

### 市场类型对比报告

代码位置：[src/ploymarket_sim/market_type_report.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/market_type_report.py)

- 新增 `market-type-report` 命令，使用本地 SQLite 历史按市场类型分别回测。
- 输出 `data/market_type_report.csv`。
- 目标是避免把长期目标、单日目标、日内区间、间接事件混成一个 PnL，从而误判策略是否有效。
- 当前观察：`price_target_daily` 已被单独识别，但旧 BUY_YES 动量策略还没有在这类市场产生交易，需要单独设计短周期/边界策略。

### BTC 动量过滤器

代码位置：[src/ploymarket_sim/backtest.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/backtest.py)

默认过滤条件：

- `YES >= 0.50`
- BTC 过去 1 小时收益 `<= -0.25%`

命中时，不允许做多 YES。该过滤器来自 `edge-report` 的坏条件分层，用于先排除明显差的交易环境。

### 每日复盘报告

代码位置：[src/ploymarket_sim/daily_report.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/daily_report.py)

- 汇总 paper report、离线回放、alignment、edge report。
- 输出 `data/daily_report.csv`。
- 给出 `not_ready` / `candidate` 状态和原因。

### 一键研究流水线

脚本位置：[scripts/research_cycle.sh](/Users/pizza_yang/code/ploymarket/scripts/research_cycle.sh)

- 依次运行模拟盘扫描、复盘、YES/NO 价差扫描、BTC 价格更新、alignment、edge、离线回放、市场类型对比、数据质量和日报。
- 主观察命令现在使用 `--market-type all`，以免短周期 BTC 市场被分类出来但没有进入模拟观察闭环。
- 适合后续接入 cron 或其他本地调度器。

### macOS 定时任务

脚本位置：

- [scripts/install_research_cycle_launchd.sh](/Users/pizza_yang/code/ploymarket/scripts/install_research_cycle_launchd.sh)
- [scripts/uninstall_research_cycle_launchd.sh](/Users/pizza_yang/code/ploymarket/scripts/uninstall_research_cycle_launchd.sh)

当前本地定时任务每 5 分钟运行一次 `research_cycle.sh`，日志写入 `logs/`。脚本内部有锁，上一轮没结束时会跳过本轮，避免重叠。

### macOS 系统防睡眠设置

推荐用系统电源设置实现“屏幕可以熄灭，但接电源时系统不睡眠”：

```bash
sudo pmset -c sleep 0 disksleep 0 displaysleep 5
```

检查：

```bash
pmset -g custom
```

重点看 `AC Power` 下 `sleep=0`、`disksleep=0`。不要合盖。

### 信号生成

代码位置：[src/ploymarket_sim/signals.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/signals.py)

当前信号是简单均线动量：

- 计算短窗口均价和长窗口均价。
- 计算 `gross_edge` 和扣除 Taker fee、滑点、安全边际后的 `net_edge`。
- 如果短期均值明显高于长期均值，当前价格没有太接近 1，且 `net_edge` 达到门槛，生成 `BUY_YES`。
- 如果 `price_range_daily` 的短期均值明显低于长期均值，且 NO 侧扣除成本后仍有净 edge，生成 `BUY_NO`。
- 如果短期均值明显低于长期均值但 NO 侧不满足条件，生成 `AVOID`。
- 其他情况为 `HOLD`。

成本估算代码位置：[src/ploymarket_sim/costs.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/costs.py)

### BTC 行情状态过滤

代码位置：[src/ploymarket_sim/btc_regime.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/btc_regime.py)

- 使用 BTC 5 分钟 K 线计算过去 `15m`、`1h`、`3h` 收益和 `1h` 高低区间。
- 输出 `uptrend`、`downtrend`、`range_bound`、`volatile`、`neutral` 或 `unknown`。
- 该过滤器不是预测模型，只负责挡掉明显逆势的短周期方向单。
- `above` 市场中，`range_bound` 且 BTC 仍低于 strike 时阻止追 `BUY_YES`；`uptrend` 且 BTC 接近或站上 strike 时阻止 `BUY_NO`。
- `below/under` 市场中，规则反向处理：下跌趋势接近或跌破 strike 时阻止 `BUY_NO`，上涨趋势时阻止追 `BUY_YES below`。
- 旧的 BTC 下跌过滤器现在只过滤 `BUY_YES`，避免误伤 BTC 下跌时合理的 `BUY_NO`。

### 执行计划

代码位置：[src/ploymarket_sim/execution.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/execution.py)

`paper-run` 现在会在信号之后生成执行计划：

- `TAKER`: `BUY_YES` 信号已经在扣除 taker fee、滑点和安全边际后达标。
- `MAKER`: gross edge 为正，但 taker 成本后不达标，只适合作为更低限价的挂单候选。
- `SKIP`: 不交易。

Maker 参数位于 `config/default.toml` 的 `[execution]` 区块。当前默认 `maker_enabled = false`，因为本地小样本中启用 Maker 成交模拟会显著恶化回测结果。

### 执行压力模拟

代码位置：[src/ploymarket_sim/execution_stress.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/execution_stress.py)

每个实时 `TAKER` 候选还会生成一份独立的 `execution_stress_<timestamp>.csv`：

- `latency_adverse_*` 用价格向不利方向变化模拟发单与网络延迟，edge 不再过线时标记 `REJECT_NEW_ORDER`。
- `partial_fill_*` 模拟只成交部分仓位，未成交残量超过阈值时标记 `CANCEL_REMAINDER`。
- `signature_or_auth_failure`、`balance_or_allowance_failure`、`cancel_failure_after_partial_fill` 模拟操作故障，并给出暂停新单或冻结单市场的 fail-safe 动作。

该报告目前是影子评估，不改写主 paper PnL，也不发送订单。参数位于 `[execution_stress]`，下一步需用积累的实时候选判断哪些门槛应提升为硬拦截。

### 风控

代码位置：[src/ploymarket_sim/risk.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/risk.py)

当前风控规则包括：

- `max_position_usdc`: 单笔最大投入。
- `max_market_exposure_usdc`: 单个市场最大敞口。
- `max_total_exposure_usdc`: 总持仓敞口。
- `max_open_positions`: 最大同时持仓数。
- `paper_reentry_cooldown_seconds`: 模拟盘同一市场止损后再次入场前的冷却时间。
- `paper_take_profit_reentry_cooldown_seconds`: 止盈后同市场短冷却；止盈是落袋为安，不代表完全停止交易。
- `daily_loss_limit_usdc`: 日内亏损上限。
- `max_drawdown_pct`: 最大账户回撤。
- `stop_loss_pct`: 单笔止损比例。
- `take_profit_pct`: 主回测/策略的单笔全量止盈比例，当前恢复为 `35%`，避免过早卖掉历史上贡献主要收益的赢家。
- `partial_take_profit_pct` / `partial_take_profit_fraction`: 浮盈达到阈值后先卖出一部分，剩余仓位继续跟踪。
- `paper_full_take_profit_pct`: 模拟盘保护性全量止盈比例，当前为 `25%`，与回测趋势止盈分开配置。
- `trailing_stop_activation_pct` / `trailing_stop_drawdown_pct`: 浮盈达到启动阈值后，如果从峰值回吐过多，则保护性退出剩余仓位。
- `paper_reentry_edge_multiplier`: 止盈后同市场重新入场需要更高 edge，避免频繁止盈/再开仓把利润交给手续费。
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
- `replay-backtest` 复用同一套回测逻辑，但只读取 SQLite 本地数据。

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

当前 Maker 未成交路径：

```text
created -> submitted -> accepted -> canceled
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
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml replay-backtest
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml paper-run
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml btc-price
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml alignment-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml edge-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml daily-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml explain-risk
```

### Paper Run

代码位置：[src/ploymarket_sim/paper.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/paper.py)

- 执行一轮模拟盘信号扫描。
- 默认适合按 `price_target` 市场运行。
- 实时链必须使用 live 市场发现与 live CLOB 数据；SQLite 仅保存观察结果和持仓状态，不作为 VPS 新开仓的旧价回退来源。
- 输出 `data/paper_run_<timestamp>.csv`。
- 同轮输出 `data/execution_stress_<timestamp>.csv` 执行风险影子报告。
- `paper-loop` 可以按固定间隔重复执行 `paper-run`。
- CSV 包含 `execution_mode`、`execution_side`、`limit_price`、`expected_net_edge` 和 `execution_reason`。

### Paper Report

代码位置：[src/ploymarket_sim/paper_report.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/paper_report.py)

- 聚合已有 `paper_run_*.csv`。
- 输出 `data/paper_report.csv`。
- 跟踪每轮信号数量、最佳 net edge 和最佳候选市场。
- 跟踪每轮 `TAKER`、`MAKER`、`SKIP` 数量。

## 当前限制

- 没有真实订单执行。
- 有持续 `paper-loop`，但还没有系统级守护进程、告警和自动日报。
- SQLite 已用于保存 paper-run 快照/持仓与 replay-backtest 离线回放，但严格实时链不使用历史缓存替代 live 开仓数据。
- 已有 BTC/Polymarket 时间对齐报告，但还没有按信号、市场类型、流动性分层评估 edge。
- 已有第一版 edge 分层报告、资金流扫描和 BUY_NO/反转实验；`BUY_NO` 已进入候选执行层，但还没有通过足够长时间的模拟盘稳定性验证。
- 没有盘口深度模拟。
- 没有考虑到期结算和市场 resolution 风险。
- 已接 BTC 现货 K 线，并开始用于 strike 距离诊断，但还没有把动态距离模型纳入正式执行层。
- 当前信号很初级，不能直接作为实盘依据。
- 当前费用模型已经读取市场级 fee rate，但仍然没有读取更复杂的 maker rebate、reward 和真实成交路径费用。
- Maker/Taker 已在执行计划层分离，Maker 已支持限价挂单、TTL 取消和价格触及成交；但还没有盘口排队位置、部分成交和更真实的成交概率。
- 市场分类还是关键词规则，后续要用真实样本不断修正。
- 逐 bar mark-to-market 已实现，但仍基于当前 CLOB 历史价格，不包含盘口深度和成交概率。
- 已有第一阶段的失败、撤单和部分成交影子压力场景，但还没有 pending/partial-filled 实时订单状态持久化、链上 settlement 查询和真实订单对账。

## 知识库状态

`docs/` 现在同时承担两个角色：

- GitHub 文档目录。
- Obsidian vault。

Obsidian 入口是：[00-home.md](/Users/pizza_yang/code/ploymarket/docs/00-home.md)

## 重要原则

进入实盘之前，必须先满足：

- 模拟盘稳定运行至少数周。
- 本地样本覆盖足够多的市场、行情阶段和结算结果。
- 每笔交易有可解释原因。
- 每次亏损都能归类。
- 风控能自动阻止继续扩大亏损。
- 真实小仓位测试的滑点和成交情况可接受。

当前策略执行条件集中记录在 [BTC 策略执行条件](/Users/pizza_yang/code/ploymarket/docs/strategy/btc-execution-conditions.md)。核心原则是：不硬编码固定 strike，而是动态结合 BTC 现货距离、`above/under` 方向、资金流、盘口成本和风控状态。
