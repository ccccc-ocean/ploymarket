# 学习进度记录

## 2026-05-07

### 本次目标

先做一个只读、模拟盘优先的 BTC 预测市场研究工具，不接实盘，不使用私钥，不下真实订单。

### 已完成

- 明确第一阶段目标：抓 BTC 相关预测市场数据，生成信号，做模拟盘和回测。
- 创建 Python 项目骨架。
- 接入 Polymarket 公开只读接口：
  - Gamma API 用于市场发现。
  - CLOB `prices-history` 用于价格历史。
- 实现基础信号：
  - `BUY_YES`: 短期隐含概率强于长期均值。
  - `HOLD`: 没有足够优势或盈亏比不合适。
  - `AVOID`: 短期隐含概率转弱。
- 实现基础风控：
  - 单笔仓位上限。
  - 单市场敞口上限。
  - 总敞口上限。
  - 最多持仓数量。
  - 日内亏损上限。
  - 最大回撤限制。
  - 单笔止损和止盈。
  - 价格区间和价差过滤。
- 跑通真实只读市场发现、信号扫描和回测。
- 创建 GitHub 仓库并推送初始代码：
  - https://github.com/ccccc-ocean/ploymarket

### 当前理解

我们的长期目标是实盘盈利，但现在最重要的是确认三件事：

- 策略是否真的有可复现优势。
- 风控是否能阻止明显错误扩大。
- 数据和执行链路是否稳定。

现阶段不追求“自动赚钱”，先追求“每个信号都能解释，每次亏损都能复盘”。

### 下次继续

建议下一次从这里开始：

1. 运行 `discover`，看看当前有哪些 BTC 市场。
2. 运行 `signals`，观察有没有 `BUY_YES`。
3. 运行 `backtest`，看 CSV 里的交易是否符合直觉。
4. 调整 `config/default.toml` 里的风控参数。
5. 为一次模拟盘实验新增 `docs/records/YYYY-MM-DD-paper-session.md`。

### 待解决问题

- 公共 API 偶尔连接截断，需要后续加入本地缓存和更细的错误分类。
- 当前信号只是简单动量，不代表稳定 edge。
- 回测仍很粗糙，没有严格模拟盘口深度、成交概率和市场到期结算。
- 还没有持续运行的 paper trading loop。

## 2026-05-07 补充：Polymarket 底层机制学习

### 本次新增资料

- 阅读并整理了 @MrRyanChi 关于 Polymarket 底层机制的长文。
- 可访问转载来源：<https://www.chaincatcher.com/article/2262869>
- 已整理为知识库文档：[Polymarket 底层机制知识库](../strategy/polymarket-market-structure.md)

### 关键收获

- Polymarket 是链下 CLOB + 链上结算的混合架构。
- 下单是签名意图，不等于立即链上成交。
- Maker / Taker 在速度、费用和风险上很不一样。
- Split / Merge / Redeem 会让简单 PnL 统计失真。
- Taker 手续费使用 `p * (1 - p)` 曲线，未来回测必须纳入。
- 实盘系统必须有订单状态机，不能把 API 返回成功直接当最终成交。

### 对项目的影响

- 下一步优先给回测加入更真实的费用和滑点。
- 设计模拟盘订单状态机，为未来实盘打底。
- 把 API 错误、维护窗口和成交失败作为系统风险处理。

## 2026-05-08：把市场结构学习转成回测成本模型

### 本次目标

基于 Polymarket 市场结构文章，把“手续费、滑点和安全边际会吞掉 edge”这件事落实到项目里。

### 已完成

- 新增 `src/ploymarket_sim/costs.py`。
- 按 Polymarket Taker fee 公式估算成本：
  - `fee = notional * feeRate * p * (1 - p)`
- 在信号里区分：
  - `gross_edge`: 原始动量优势。
  - `net_edge`: 扣除 Taker fee、滑点和安全边际后的净优势。
- `BUY_YES` 现在必须满足净 edge 门槛，而不是只看 gross edge。
- 回测 CSV 新增字段：
  - `fee`
  - `slippage`
  - `net_edge`
- 回测买入金额改成费用内含，避免现金不足时因为费用导致余额为负。
- 测试从 6 个增加到 7 个，并全部通过。

### 今天观察到的真实信号现象

运行 `signals` 后，很多市场的 `gross_edge` 看起来接近或略大于 0，但 `net_edge` 扣除成本后变成负数。

这说明：

- 小 edge 在真实交易里很容易被手续费、滑点和安全边际吃掉。
- 未来实盘不能只看方向判断，还必须看扣成本后的净优势。
- 对 Taker 策略来说，`min_edge` 应该显著高于理论手续费。

### 下一步建议

1. 加本地行情缓存，减少 API 慢和截断对学习节奏的影响。
2. 给回测输出汇总统计：胜率、平均盈亏、最大回撤、总费用、总滑点。
3. 把 BTC 纯价格市场和 MicroStrategy / 公司事件类市场分开，不要混在同一个策略里评估。
4. 设计 paper order 状态机，但先不接实盘。

## 2026-05-10：引入 Obsidian 知识库工作流

### 本次目标

把本地安装的 Obsidian 用起来，让项目不只是代码仓库，也成为可持续学习的知识库。

### 已完成

- 把 `docs/` 明确作为 Obsidian vault。
- 新增知识库主页：[[../00-home|Ploymarket Knowledge Vault]]
- 新增学习地图：[[learning-map|学习地图]]
- 新增今日计划：[[2026-05-10-session-plan|2026-05-10 学习与构建计划]]
- 新增决策日志：[[../system/decision-log|决策日志]]
- 新增市场分类笔记：[[../strategy/market-taxonomy|预测市场分类笔记]]
- 新增 Obsidian 模板：
  - [[../templates/daily-learning-note|daily-learning-note]]
  - [[../templates/strategy-note|strategy-note]]
- 实现第一版市场分类器：
  - `price_target`
  - `price_range_daily`
  - `company_treasury`
  - `indirect_event`
  - `unknown`
- CLI 支持 `--market-type` 过滤。

### 今天的关键判断

下一步代码优先做“市场分类”，再做“本地缓存”。

原因：

- 当前系统会抓到纯 BTC 价格市场、MicroStrategy 事件市场和间接 BTC 市场。
- 它们不能用同一个策略信号评估。
- 如果不先分类，回测统计会混在一起，容易形成错误结论。

### 下次继续

从 [[2026-05-10-session-plan|2026-05-10 学习与构建计划]] 继续。

建议下一步：

1. 用 `--market-type price_target` 只跑价格目标市场。
2. 给回测增加汇总统计。
3. 再做本地缓存，减少 API 截断和等待。

## 2026-05-10：回测汇总统计

### 本次目标

让回测不只是输出每个市场的交易 CSV，还能直接看到整体表现和按市场类型聚合的结果。

### 已完成

- 新增 `src/ploymarket_sim/summary.py`。
- 新增 `data/backtest_summary.csv`。
- 新增 `data/backtest_summary_by_type.csv`。
- `backtest` 命令结束时会打印总览摘要。
- 汇总字段包括：
  - 市场类型。
  - 交易次数。
  - 买入次数。
  - 退出次数。
  - 风控拒绝次数。
  - 胜率。
  - 已实现盈亏。
  - 总费用。
  - 总滑点。
  - 最好/最差单笔退出。

### 当前观察

`backtest --market-type price_target` 已经能生成汇总文件。由于当前实时发现到的价格目标市场数量有限，本轮样本还不够大。

这再次说明下一步本地缓存很重要：我们需要积累更多历史查询和回测样本，减少公共 API 抖动对学习节奏的影响。

### 下次继续

优先做本地缓存，目标是：

- API 请求结果落盘。
- 同一轮学习里重复运行不反复打公共接口。
- 回测样本更稳定。

## 2026-05-10：本地 HTTP 缓存

### 本次目标

减少公共 API 慢、截断和重复请求对学习/回测的影响。

### 已完成

- 新增 `src/ploymarket_sim/cache.py`。
- 新增 `[cache]` 配置区块。
- `Gamma` 市场发现和 `CLOB prices-history` 都接入缓存。
- 成功响应写入 `.cache/http/`。
- 默认 TTL 为 `900` 秒。
- 如果远程请求失败，且存在旧缓存，会使用 stale cache。
- 新增 `cache-info` 命令。
- `.cache/` 已加入 `.gitignore`。

### 使用方式

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml cache-info
```

### 当前观察

第一次运行会请求远程 API 并写入缓存。第二次运行相同 URL 时会复用已缓存响应；没有成功缓存过的分页仍会继续请求远程。

### 下次继续

下一步建议做组合级回测资金曲线，因为现在已有：

- 市场分类。
- net edge 成本模型。
- 汇总统计。
- 本地缓存。

组合级资金曲线可以帮助我们看真正的账户级回撤。

## 2026-05-10：组合级回测资金曲线

### 本次目标

把单市场回测结果合并成一个组合账户视角，开始观察账户级 PnL、费用、滑点和最大回撤。

### 已完成

- 新增 `src/ploymarket_sim/portfolio.py`。
- `backtest` 命令新增输出：
  - `data/portfolio_curve.csv`
  - `data/portfolio_summary.csv`
- 组合曲线字段包括：
  - 现金。
  - 已投入本金。
  - 账户净值。
  - 峰值净值。
  - 回撤。
  - 单事件费用和滑点。
- 新增组合级终端摘要。

### 本轮 price_target 回测观察

本轮 `backtest --market-type price_target`：

- 参与回测市场：33 个。
- 有交易市场：5 个。
- 交易事件：20 个。
- 胜率：40.0%。
- 组合 PnL：`-0.87`。
- 最大回撤：`2.8%`。
- 总费用：`2.30`。
- 总滑点：`0.62`。

### 当前口径

组合曲线目前是交易事件级别，不是逐 bar mark-to-market。

持仓按投入本金计值，费用和滑点立即降低净值。这是一个保守但还不够精细的口径。

### 下次继续

建议下一步做 paper order 状态机，为未来持续模拟盘和实盘订单生命周期打基础。

## 2026-05-10：Paper Order 状态机

### 本次目标

让模拟盘开始记录订单生命周期，而不只是记录最终交易结果。

### 已完成

- 新增 `src/ploymarket_sim/orders.py`。
- 回测买入、卖出、回测结束平仓都会生成订单事件。
- 风控拒绝会生成拒绝事件。
- 新增输出：
  - `data/orders_<market_id>.csv`
  - `data/orders_all.csv`

### 当前状态路径

正常模拟成交：

```text
created -> submitted -> accepted -> matched -> settled
```

风控拒绝：

```text
created -> rejected
```

### 为什么重要

Polymarket 真实下单不是“API 返回成功就等于最终成交”。未来实盘系统需要区分 submitted、matched、settled、failed、canceled 等状态。

我们现在先在模拟盘里建立这个习惯，之后接真实订单时不会重构整个账本。

### 下次继续

建议下一步读取市场真实 fee 设置，替换当前默认的 `taker_fee_rate = 0.02` 估算值。

## 2026-05-10：市场级真实 fee rate

### 本次目标

把费用模型从固定默认值推进到市场级 fee rate，降低回测成本低估的风险。

### 已完成

- `Market` 新增：
  - `fees_enabled`
  - `taker_fee_rate`
  - `fee_type`
- 从 Polymarket market 对象解析 `feeSchedule.rate`。
- 信号和回测优先使用市场级 fee rate。
- 如果市场没有 fee schedule，则回退到配置里的 `backtest.taker_fee_rate`。
- `discover` 输出显示 `fee=...`。
- `backtest_summary.csv` 新增 `taker_fee_rate` 字段。

### 本轮 price_target 回测观察

市场级 fee rate 接入后，很多价格目标市场显示 `fee=0.070`，明显高于之前默认的 `0.020`。

本轮 `backtest --market-type price_target`：

- 参与回测市场：35 个。
- 有交易市场：4 个。
- 交易事件：14 个。
- 胜率：57.1%。
- 组合 PnL：`+10.25`。
- 最大回撤：`1.5%`。
- 总费用：`5.89`。
- 总滑点：`0.44`。

### 当前理解

更真实的费用并不只是让 PnL 下降，它还会改变哪些交易能通过 `net_edge` 门槛。也就是说，费用模型会改变策略行为本身。

### 下次继续

建议下一步做 SQLite 行情库，把 HTTP cache 升级成结构化 market/history 存储，为长期模拟盘积累数据。
