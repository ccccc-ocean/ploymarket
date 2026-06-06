# 当前系统状态

最后更新：2026-06-04

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
- `paper-run` 和 `spread-scan` 是实时扫描：必须使用 live 市场；VPS 严格实时配置的 `fresh_market_ttl_seconds=0`，live discovery 不足时不生成新开仓依据。实时健康度只检查本轮活跃 live 覆盖，不拿不断累积的历史研究市场数当分母。
- `paper-run` 的价格历史和 `spread-scan` 的订单簿仍必须实时拉取；历史缓存只用于离线研究和回测。
- Kalshi 依赖已从主线移除：当前研究只使用 Polymarket live/CLOB 数据和 Coinbase BTC 现货，避免跨平台口径差异扰乱策略迭代。
- `replay-backtest` 可以只使用 SQLite 本地数据离线回放。
- `data-quality` 输出本地市场和历史价格覆盖情况。
- `paper_snapshots` 保存每轮模拟盘信号和执行计划。
- `paper_positions` 保存实时模拟盘的同市场持仓状态；已有模拟持仓时不会每轮重复 TAKER，分批止盈会降低仓位，止盈后短冷却，止损后长冷却。
- `paper_position_history` 保存每笔已关闭模拟仓位的历史快照；同市场冷却后重新开仓不再覆盖此前的已实现盈亏记录。
- `paper-run` 的新开仓候选必须来自当轮 live discovery；但任何尚未关闭的模拟仓位即使不在当轮发现列表中，也必须继续用实时历史和订单簿检查退出条件，避免风险敞口失去监控。
- 已有模拟仓位若订单簿不再可用，会查询实时 Gamma 市场状态；仅在市场明确 `closed` 且 `resolved`、最终 outcome 为 `0/1` 时按兑付价值关闭账本，避免到期仓长期停留为未关闭状态。
- 已有模拟仓位若市场 `end_date` 已经过期，也会优先查询实时 Gamma resolved 状态；如果市场仍未 resolved，则继续按实时 bid 管理，不手工猜测结算结果。
- `stale_tokens` 记录最近 CLOB 404 的 token，避免 `spread-scan` 反复扫描已失效订单簿。
- `paper_probe` 探索仓按家族单独归因；亏损家族会自动停用，已停用家族的未平仓探索仓会按实时 bid risk-off 退出，避免为了补样本继续持有坏设计。
- 2026-06-03 新增 `touch_below_certainty_no` 小仓探索家族，用于验证 below/dip 目标还有安全距离、NO 高确定性但仍有实时净 edge、BTC 没有明显下跌加速的场景。
- 2026-06-03 收紧 `above_below_expiry/BUY_NO` 临界 strike 规则：BTC 在 above strike 安全带内但没有明显远离时，不再允许主仓开 NO；near-strike 探索仓也必须看到 BTC 从 strike 退开。
- 2026-06-03 新增 `open-position-report`：结构化输出当前未平仓模拟仓位、探针家族、到期状态、实时/存储价格来源、浮动 PnL 和估算总 PnL。VPS live 周期会用 `--live-quotes` 生成 `runtime/data/open_position_report.csv`，用于区分“没有正 edge 所以不开仓”和“持仓/结算/风控卡住导致不开仓”。
- 2026-06-03 针对连续 100+ 轮零 TAKER 的样本饥饿问题，新增 `certainty_above_below_yes` 与 `recovery_above_below_no` 两类 3 USDC 级别小仓探测。触发条件基于相对 strike 距离、15m/1h BTC 是否朝失效方向移动、NO/YES 价格上限和实时 ask 重定价后的 net edge；不硬编码任何固定 strike。该调整只用于恢复前瞻样本密度，不代表放宽实盘门槛。
- 2026-06-03 进一步新增 `ultra_certainty_above_below_yes` 1 USDC 微型探测，用于 YES 价格较高、利润空间薄但 BTC 明显远离 above strike 的场景。该家族允许轻微回落，但要求 spot 与 strike 有更大安全距离；它只为增加“高确定性薄利结构”的前瞻样本，亏损时应提高 edge/距离要求，不能扩大仓位。
- 2026-06-03 对称新增 `ultra_certainty_above_below_no` 1 USDC 微型探测，用于 NO 价格接近 1、利润空间薄但 BTC 明显低于 above strike 且没有快速反抽的场景。该家族独立统计，不能混入普通 `certainty_above_below_no`。
- 2026-06-03 VPS live paper 扫描从每 5 分钟调整为每 2 分钟。目的不是放宽策略，而是减少短暂正 edge 窗口被采样间隔错过；`live_paper_cycle` 仍有 lock，上一轮未结束时会自动跳过新 tick，避免重叠运行。
- 2026-06-03 新增探针家族复盘约束：`regime_filter_challenge` 只有在 BTC 明确远离 strike 后才允许重设计恢复；`touch_below_no` 出现单笔大亏后会停用并要求更大 target 距离、非加速下跌和临近到期高价 NO 限制后再恢复。
- 默认路径：`data/ploymarket.sqlite`
- SQLite 文件已加入 `.gitignore`。

查看存储：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml storage-info
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml data-quality
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml open-position-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml live-universe-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml blocked-edge-report
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml touch-below-path-report
```

### 市场分类

代码位置：[src/ploymarket_sim/classifier.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/classifier.py)

- `up_down_short_term`: 短周期 Up/Down 方向市场。
- `above_below_expiry`: 到期时 above/below 某个 strike 的市场。
- `range_bucket`: 到期落在某个价格区间的 bucket 市场。
- `touch_above`: 路径触碰上方目标，例如 reach/hit 某个高价。
- `touch_below`: 路径触碰下方目标，例如 dip/drop 某个低价。
- `expiry_target`: 目标价但无法明确归入触碰或到期口径的市场；默认更保守。
- `company_treasury`: MicroStrategy / MSTR / 公司 BTC 持仓事件市场。
- `indirect_event`: 只和 BTC 间接相关的市场。
- `unknown`: 第一版规则无法判断的市场。

CLI 支持：

```bash
PYTHONPATH=src python3 -m ploymarket_sim.cli --config config/default.toml discover --market-type above_below_expiry
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
- 对同一批 `above_below_expiry` 历史并排比较：
  - `YES_ONLY_SL25`
  - `YES_NO_SL25`
  - `YES_NO_REV_SL25_CD60M`
  - `YES_NO_REV_SL15_CD60M`
  - `YES_NO_REV_SL12_CD60M`
- 输出 `data/reversal_summary.csv` 和 `data/reversal_trades.csv`。
- 第一轮实验显示：允许 `BUY_NO` 明显改善当前样本，但把止损收紧到 `12%/15%` 会产生更多噪音交易并恶化 PnL。
- 反转不是无脑反手，必须重新满足反向净 edge；否则会在 5 分钟市场里被来回扫损。
- `BUY_NO` 已从单独实验升级到主候选策略层：`signals`、`execution`、`backtest`、`portfolio`、`paper-run` 和 `paper-report` 都能识别 `BUY_NO`。
- 主候选策略重点在 `above_below_expiry` 市场允许 `BUY_NO`，并按 NO 价格自身做价格上下限过滤，避免把 1 cents 翻转玩法混进 BTC 主策略。
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
- 当前观察：`touch_below` 与 `expiry_target` 已从旧目标市场中拆出，但默认观察；只有 `touch_above` 允许保守 `BUY_NO` 候选。

### BTC 动量过滤器

代码位置：[src/ploymarket_sim/backtest.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/backtest.py)

默认过滤条件：

- `YES >= 0.50`
- BTC 过去 1 小时收益 `<= -0.25%`

命中时，不允许做多 YES。该过滤器来自 `edge-report` 的坏条件分层，用于先排除明显差的交易环境。

### 入场质量过滤

代码位置：

- [src/ploymarket_sim/market_rules.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/market_rules.py)
- [src/ploymarket_sim/strategy_profiles.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/strategy_profiles.py)
- [src/ploymarket_sim/cli.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/cli.py)

当前模拟盘在开仓前会额外执行：

- `above_below_expiry` 重点允许 `BUY_NO`，因为当前样本中失败突破/未能站上 strike 的 NO 侧更稳定；`BUY_YES` 暂时观察。
- `up_down_short_term` 允许双边，但使用更短窗口和更高的 edge 要求，避免把长期目标策略硬套到短周期市场。
- `range_bucket` 暂时降为观察模式；VPS 样本显示它需要双边界模型，直接套单边动量会产生过多交易和费用。
- `touch_above` 只允许更保守的 `BUY_NO`；`touch_below` 与 `expiry_target` 当前默认观察，不主动开仓。
- `above_below_expiry BUY_NO above` 如果 BTC 在安全带内且正在接近/突破 strike，会暂停逆突破方向。
- 实时订单簿 ask 重定价后，净 edge 必须至少达到 `min_edge * live_reprice_edge_multiplier`；默认倍数为 `2.0`。
- 连续亏损暂停按 `market_type + strike direction + side` 统计，减少不同方向策略互相误伤，同时能更快暂停同类亏损模式。

### 策略复盘原则

文档位置：[docs/strategy/anti-overfit-review-principles.md](/Users/pizza_yang/code/ploymarket/docs/strategy/anti-overfit-review-principles.md)

- 后续策略修复禁止针对固定价格点做特殊适配。
- 具体亏损市场只能作为案例，最终规则必须落到相对变量：`strike_distance_pct`、BTC regime、距离到期时间、盘口成本、流动性、资金流、连续亏损簇等。
- 每次修复前必须先判断问题属于趋势识别、震荡噪音、赔率过薄、执行延迟、重复入场、统计口径或数据质量中的哪一类。
- 修复后不能只看单轮 `replay_pnl`，必须同时看 `paper_account_pnl`、交易数、最大回撤、连续亏损和亏损集中度。

### 每日复盘报告

代码位置：[src/ploymarket_sim/daily_report.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/daily_report.py)

- 汇总 paper report、离线回放、alignment、edge report。
- 输出 `data/daily_report.csv`。
- `replay_pnl` 表示离线回放/历史样本 PnL，会包含当前日期之前已经到期的回放市场。
- `paper_account_pnl` 表示模拟盘账户账本里的已实现 PnL，来自 SQLite 的已关闭仓位和开仓仓位中已部分止盈落袋的收益；不包含未平仓浮盈浮亏。
- 给出 `not_ready` / `candidate` 状态和原因。
- 实时模拟链的健康状态缺失、失败或超时未成功时，强制维持 `not_ready`。

### 一键研究流水线

脚本位置：[scripts/research_cycle.sh](/Users/pizza_yang/code/ploymarket/scripts/research_cycle.sh)

- 依次运行模拟盘扫描、复盘、YES/NO 价差扫描、BTC 价格更新、alignment、edge、离线回放、市场类型对比、数据质量和日报。
- 主观察命令现在使用 `--market-type all`，以免短周期 BTC 市场被分类出来但没有进入模拟观察闭环。
- 适合后续接入 cron 或其他本地调度器。

### VPS 无人值守健康监控

脚本位置：

- [scripts/live_paper_cycle.sh](/Users/pizza_yang/code/ploymarket/scripts/live_paper_cycle.sh)
- [scripts/watchdog_cycle.sh](/Users/pizza_yang/code/ploymarket/scripts/watchdog_cycle.sh)
- [src/ploymarket_sim/pipeline_health.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/pipeline_health.py)

VPS 实时链和深度链会在 `runtime/data/health/` 写入状态。watchdog 每五分钟错峰检查，自动重试失败或过期链路，并清除没有存活进程的遗留锁。实时链失败会直接阻断 `readiness`；持续代码错误仍需修复后重新验证，不会被自动重试伪装成健康。

### macOS 定时任务

脚本位置：

- [scripts/install_research_cycle_launchd.sh](/Users/pizza_yang/code/ploymarket/scripts/install_research_cycle_launchd.sh)
- [scripts/uninstall_research_cycle_launchd.sh](/Users/pizza_yang/code/ploymarket/scripts/uninstall_research_cycle_launchd.sh)

本地定时任务目前已暂停，避免与 VPS 前瞻样本混淆；持续模拟盘与健康监控以 VPS 为准。

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
- 如果 `above_below_expiry` 的短期 YES 均值明显低于长期均值，且 NO 侧扣除成本后仍有净 edge，生成 `BUY_NO`。
- `expiry_target` 和 `touch_below` 当前即使出现薄 edge，也先 HOLD，直到有足够跨日期样本证明该结构值得交易。
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
- `shadow_order_events_<timestamp>.csv` 输出 `SUBMITTED`、`FILLED`、`CANCELED_UNFILLED`、`PARTIALLY_FILLED`、`CANCELED_REMAINDER`、`CANCEL_PENDING` 与 `REJECTED` 事件；撤单待确认时仍预留完整名义敞口。
- `execution_stress_report.csv` 汇总所有实时轮次的候选数、延迟压力通过数、部分成交撤单数和 fail-safe 数。

主 paper 路径以实时 ask 下可立即成交作为基线；延迟恶化、`FOK` 未成交、`FAK` 部分成交和订单故障作为并行影子评估，不再用固定压力情景直接删除主策略样本。系统不发送真实订单；下一步需为执行路径分别计算 PnL，并将跨轮未确认影子订单持久化。

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
- `readiness_max_drawdown_pct`: 进入“候选可观察”状态的回撤阈值，当前为 `10%`。这不是实盘开关，只是避免模拟盘在 `8%` 附近被过早卡死。
- `stop_loss_pct`: 单笔止损比例，当前为 `20%`，比之前 `25%` 更早砍掉错误方向。
- `take_profit_pct`: 主回测/策略的单笔全量止盈比例，当前恢复为 `35%`，避免过早卖掉历史上贡献主要收益的赢家。
- `partial_take_profit_pct` / `partial_take_profit_fraction`: 浮盈达到阈值后先卖出一部分，剩余仓位继续跟踪。当前为 `16%` 先卖 `35%`，减少过早切掉赢家。
- `paper_full_take_profit_pct`: 模拟盘保护性全量止盈比例，当前为 `32%`，与回测趋势止盈分开配置。
- `trailing_stop_activation_pct` / `trailing_stop_drawdown_pct`: 浮盈达到启动阈值后，如果从峰值回吐过多，则保护性退出剩余仓位。当前为浮盈 `18%` 后允许从峰值回吐 `7%`。
- `range_buy_yes_max_price` / `range_buy_no_max_price`: `above_below_expiry` / `range_bucket` 入场价格上限，当前分别为 `0.88` / `0.75`，用于避免高价追单。
- `range_market_safety_band_pct` / `btc_moving_away_return_pct`: strike 安全带与 15 分钟方向过滤；BTC 在安全带内朝 strike 快速移动时，不逆势开另一边。
- `strategy_loss_pause_count` / `strategy_loss_pause_window_seconds`: 同类型同方向连续亏损熔断；当前为 `6` 小时内亏损达到 `2` 笔后暂停该类型/方向新开仓。
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
- 默认按 `all` 运行，再由市场分类、策略 profile 和风控过滤决定是否开仓。
- 实时链必须使用 live 市场发现与 live CLOB 数据；SQLite 仅保存观察结果和持仓状态，不作为 VPS 新开仓的旧价回退来源。
- 输出 `data/paper_run_<timestamp>.csv`。
- 同轮输出 `data/execution_stress_<timestamp>.csv` 执行风险影子报告。
- 同轮输出 `data/shadow_order_events_<timestamp>.csv`，并维护累计 `data/execution_stress_report.csv`。
- `paper-loop` 可以按固定间隔重复执行 `paper-run`。
- CSV 包含 `execution_mode`、`execution_side`、`limit_price`、`expected_net_edge` 和 `execution_reason`。
- 当前 `paper_probe` 不再等待连续零成交才触发；只要 probe 风控容量允许，就可以开极小探索仓来增加前瞻样本。当前单笔 3 USDC，最多 5 笔软 probe 持仓、10 笔硬上限，总 probe 暴露上限 30 USDC，每轮最多新增 3 笔。
- `paper_probe` 只用于模拟盘验证过滤器和观察市场，不代表主策略已通过实盘条件。
- 2026-06-04 主策略 paper sizing 从 25 USDC 降为 3 USDC。原因是样本恢复阶段需要更多均匀小样本，而不是让单笔主仓过度支配 `paper_account_pnl`；这不会放宽实盘门槛。
- `above_below_expiry` 的样本恢复优先验证两类相对结构：BTC 明显站在 above strike 上方且没有快速回落时的高确定性 `BUY_YES`，以及旧高价 NO 家族停用后、BTC 仍明显低于 above strike 且没有向 strike 反抽时的小仓 `BUY_NO`。两者都必须单独按 probe family 复盘 PnL、止损率和平均盈亏。
- 对 YES 约 `0.90-0.965` 的薄利场景，只允许 1 USDC 微型探测，并要求 BTC 相对 strike 有更大距离、15m/1h 没有剧烈回落、实时 ask 后仍有正 edge。
- 对 NO 约 `0.94-0.999` 的薄利场景，只允许 1 USDC 微型探测，并要求 BTC 明显低于 above strike、没有快速向 strike 反抽、实时 ask 后仍有正 edge。
- `range_bucket_yes` 旧家族因历史亏损停用后，不再直接复活。2026-06-04 新增 `range_bucket_center_yes` 1 USDC 微型家族：只在 BTC 位于区间中心、到上下边界有足够安全距离、1 小时波动温和且实时 edge 足够时验证。它用于恢复 range_bucket 的前瞻样本，不代表 range_bucket 可进入主策略。
- 2026-06-04 live universe 复查显示当前实时市场主要是 `above_below_expiry`、`touch_above`、`touch_below`，暂时没有 live `range_bucket`。因此 range_bucket 的零开仓不是单纯过滤过严，而是缺少实时可交易对象；不能用本地历史 range 市场强行验证。
- 2026-06-04 新增 `live-universe-report`：直接用当轮实时 Polymarket discovery，不回退 SQLite 历史市场，并和最近 `paper_run` 样本统计拼接。它用于区分 `no_live_markets`、`sample_starved_with_live_markets`、`live_with_blocked_edge`，防止把“当前没有该类型实时市场”误判成“过滤器过严”。
- 2026-06-04 新增 `blocked-edge-report`：按 `market_type + market_id + reason_bucket` 聚合最近正 edge 但被 SKIP 的候选，并标记同一市场后来是否已有 TAKER。它用于判断“被过滤的机会是否后来已由更保守探针进场”，避免为了提高开仓数重复放宽已经验证过的市场。
- 2026-06-04 新增 `touch-below-path-report`：把 `touch_below` 市场按 BTC 与目标价距离、15m/1h 现货动量、YES/NO 价格状态分成 `falling_toward_target`、`too_close_to_target_for_no`、`yes_near_resolved_or_triggered`、`distance_no_probe_candidate` 等状态。VPS 最近样本显示 touch_below 零开仓主要是 BTC 正在向目标下跌或已离目标过近，不适合为了样本硬开 NO。
- 2026-06-04 新增 `touch_below_distance_no` 1 USDC 微型探针：只在 `touch_below` 出现正 edge 但主策略不足、BTC 离下方目标足够远、NO 价格中等、且 BTC 没有向目标下跌加速时验证 NO 侧。它用于等待真正安全的 touch_below 样本窗口，不复活此前亏损的 BUY_YES 家族。
- 2026-06-04 修复 `touch_below_distance_no` 的触发入口：`touch-below-path-report` 已把部分 `touch_below 暂不允许 BUY_NO` 行识别为 `distance_no_probe_candidate`，但探针函数此前只接受 `净优势不足` reason，导致有安全距离和正 edge 的候选仍然零开仓。修复后 VPS 手动验证已开出 1 笔 `Will Bitcoin dip to $60,000 June 1-7?` 的 1USDC `BUY_NO` 微型仓，实时 ask 后净 edge 约 `0.0723`。
- 2026-06-04 同步修复 probe family 归因顺序：`距离安全 touch_below/NO v1` 必须先于通用 `touch_below/NO v1` 匹配，否则新家族会被旧亏损家族 `touch_below_no` 误判并 risk-off 退出。VPS 已确认 `paper_sample_report` 中 `touch_below` 最近样本归因为 `touch_below_distance_no`。
- 2026-06-04 研究链 `alignment-report --market-type all` 曾反复在 VPS 上超时。根因不是实时行情链，而是每小时对 SQLite 中全量市场和全量价格历史做 alignment，且旧算法对每个点线性查找未来价格/BTC candle。已将 alignment 查找改为 timestamp 二分，并给 CLI 增加 `--max-points-per-market`；`research_cycle.sh` 默认每个市场只取最近 `600` 个点，保持近期 edge/daily 复盘新鲜。全量 alignment 应作为低频离线任务单独运行，不能阻塞实时模拟盘。
- 2026-06-04 `strategy-sweep` 也改为支持 `--max-points-per-market`，`research_cycle.sh` 默认使用最近 `600` 个点和 `candidate-limit=2` 做轻量参数巡检。VPS 实测轻量 sweep 约 `94s`；深度 sweep 仍应作为低频离线任务，不应每轮阻塞 research 收尾。
- 2026-06-04 SQLite 存储层增加连接 `busy_timeout=30000`，并让同一 `Storage` 实例只执行一次 schema 初始化，减少 live/research 并发时的 `database is locked` 和重复 DDL 压力。
- 2026-06-04 新增 `crossed_above_reversal_no` 1 USDC 微型探针：只在 `above_below_expiry` 的 above 市场里，BTC 已经略高于 strike、YES 动量转弱、NO 仍有正 edge、1h BTC 走弱且 15m 没有强上涨加速时验证 NO 侧。它用于增加“假突破/回落”样本，不等同于放宽主策略；VPS 首轮已开 1 笔 `above 62k` NO 微型仓。
- 2026-06-04 `touch_below/YES` 的 discount 与 momentum 探针均出现快速止损，已保持停用。touch 路径类 YES 在没有独立路径概率模型前不作为扩样本入口；后续第二样本来源优先等待 live range_bucket 出现，或寻找 touch/above-below 的 NO 侧正 edge。

### Paper Report

代码位置：[src/ploymarket_sim/paper_report.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/paper_report.py)

- 聚合已有 `paper_run_*.csv`。
- 输出 `data/paper_report.csv`。
- 跟踪每轮信号数量、最佳 net edge 和最佳候选市场。
- 跟踪每轮 `TAKER`、`MAKER`、`SKIP` 数量。

## 当前限制

- 没有真实订单执行。
- VPS 已有状态文件与 watchdog 自动重试；仍缺少外部告警通道和对持续代码故障的自动代码修复闭环。
- SQLite 已用于保存 paper-run 快照/持仓与 replay-backtest 离线回放，但严格实时链不使用历史缓存替代 live 开仓数据。
- 已有 BTC/Polymarket 时间对齐报告，但还没有按信号、市场类型、流动性分层评估 edge。
- 已有第一版 edge 分层报告、资金流扫描和 BUY_NO/反转实验；`BUY_NO` 已进入候选执行层，但还没有通过足够长时间的模拟盘稳定性验证。
- 没有盘口深度模拟。
- 没有考虑到期结算和市场 resolution 风险。
- 已接 BTC 现货 K 线，并开始用于 strike 距离诊断，但还没有把动态距离模型纳入正式执行层。
- 当前信号很初级，不能直接作为实盘依据。
- 2026-06-01 起为了缓解 SKIP 过多，模拟盘探索仓略微放宽；因此后续必须更重视 `paper_account_pnl`、probe 胜率、止损率和平均盈亏，不能只看交易数增加。
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
