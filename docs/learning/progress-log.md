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

## 2026-05-10：SQLite 市场与价格历史存储

### 本次目标

把短期 HTTP cache 升级为可长期积累的结构化本地数据库。

### 已完成

- 新增 `src/ploymarket_sim/storage.py`。
- 新增 `[storage]` 配置区块。
- `discover` 自动保存市场快照。
- `signals` 和 `backtest` 自动保存市场快照和价格历史。
- 新增 `storage-info` 命令。
- SQLite 文件加入 `.gitignore`。

### 当前本地数据库状态

```text
markets: 35
price_points: 5446
```

### 为什么重要

HTTP cache 解决“短时间重复请求”的问题；SQLite 解决“长期积累研究样本”的问题。

未来我们可以用 SQLite 做：

- 离线回测。
- 每日市场快照对比。
- 策略样本统计。
- 模拟盘持仓和订单日志。

### 下次继续

建议下一步做逐 bar mark-to-market 组合曲线，让回测组合净值不只在交易事件时更新。

## 2026-05-10：逐 bar Mark-to-Market 组合曲线

### 本次目标

让组合资金曲线在持仓期间根据价格历史持续重估，而不是只在买入/卖出事件时更新。

### 已完成

- 新增逐 bar mark-to-market 曲线。
- 新增输出：
  - `data/portfolio_mtm_curve.csv`
  - `data/portfolio_mtm_summary.csv`
- `backtest` 终端输出新增 `mark_to_market` 摘要。

### 本轮 price_target 回测观察

同一轮 `backtest --market-type price_target`：

- 交易事件曲线最大回撤：约 `1.5%`。
- 逐 bar mark-to-market 最大回撤：约 `1.8%`。
- 逐 bar 事件数：`292`。

这说明仅看交易事件会低估持仓期间的波动风险。

### 当前限制

逐 bar mark-to-market 仍然只用 CLOB 历史价格，不模拟盘口深度、成交概率、部分成交或真实退出难度。

### 下次继续

建议下一步做持续模拟盘 `paper-run` 命令，让系统可以按固定流程扫描、记录信号、写入数据库和输出复盘摘要。

## 2026-05-10：单轮 Paper Run

### 本次目标

让系统能执行一轮标准化模拟盘扫描，为未来 24 小时持续模拟盘做准备。

### 已完成

- 新增 `src/ploymarket_sim/paper.py`。
- 新增 CLI 命令：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml paper-run --market-type price_target
```

- 输出 `data/paper_run_<timestamp>.csv`。
- 每轮扫描会写入 SQLite 市场和价格历史。

### 本轮观察

本轮 `price_target` 扫描：

- 市场数：35。
- `BUY_YES`: 0。
- `HOLD`: 35。
- `AVOID`: 0。

### 当前意义

这说明在当前 fee、滑点和安全边际假设下，本轮没有价格目标市场达到可交易的净 edge 门槛。

### 下次继续

建议下一步做每日复盘报告，把多次 `paper-run` 的输出聚合成：

- 每日信号数量。
- BUY_YES 候选变化。
- 市场类型分布。
- 是否有连续出现的候选机会。

## 2026-05-10：Paper Report

### 本次目标

把多轮 `paper-run` 聚合成复盘报告，观察信号是否持续出现。

### 已完成

- 新增 `src/ploymarket_sim/paper_report.py`。
- 新增 CLI 命令：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml paper-report
```

- 输出 `data/paper_report.csv`。

### 当前观察

当前只有 1 轮 paper-run：

- 市场数：35。
- `BUY_YES`: 0。
- 最佳 net edge：约 `-0.0110`。

这说明在当前成本模型和安全边际下，系统没有强行产生交易机会。

### 下次继续

建议下一步做定时运行方式，让 `paper-run` 可以每隔固定时间自动执行。

## 2026-05-10：Paper Loop

### 本次目标

让模拟盘可以按固定间隔连续运行多轮。

### 已完成

- 新增 CLI 命令 `paper-loop`。
- 新增脚本：
  - `scripts/paper_run_once.sh`
  - `scripts/paper_loop.sh`

### 使用方式

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml paper-loop --market-type price_target --interval-seconds 300 --iterations 0
```

### 安全设计

`paper-loop` 默认只运行 1 轮，避免误开无限循环。只有显式传 `--iterations 0` 才会一直运行。

### 下次继续

建议下一步做 Maker/Taker 策略分离。当前系统仍然把所有 `BUY_YES` 当作 Taker 买入处理。

## 2026-05-10：Maker/Taker 执行计划分离

### 本次目标

把“信号是否有 edge”和“用什么方式下单”拆开，避免模拟盘把所有机会都粗暴当成 Taker 吃单。

### 已完成

- 新增 `src/ploymarket_sim/execution.py`。
- 新增配置区块 `[execution]`：
  - `maker_enabled`
  - `maker_price_improvement`
  - `maker_min_edge`
  - `maker_fee_rate`
  - `maker_order_ttl_seconds`
- `paper-run` 输出新增：
  - `execution_mode`
  - `execution_side`
  - `limit_price`
  - `expected_net_edge`
  - `execution_reason`
- `paper-report` 新增 `TAKER` / `MAKER` / `SKIP` 数量汇总。

### 本轮观察

本轮本地 `price_target` 扫描：

- 市场数：35。
- `BUY_YES`: 0。
- `HOLD`: 35。
- `AVOID`: 0。
- `TAKER`: 0。
- `MAKER`: 0。
- `SKIP`: 35。
- 最佳 net edge：约 `-0.0110`。

结论：当前市场没有通过成本和安全边际过滤的交易机会，系统保持不交易。

### 工程改进

本轮发现外部 API 慢请求会拖住整轮扫描，因此顺手完成两项稳定性改进：

- HTTP 请求增加运行级硬截止时间。
- `paper-run` 优先使用 SQLite 里的本地市场和历史价格，网络只作为缺失数据时的补充来源。

### 下次继续

建议下一步做 SQLite 离线回放，把多次保存的市场和价格历史变成可重复测试样本。之后再做 Maker 成交概率模型，避免把“挂单候选”误当成“必然成交”。

## 2026-05-10：SQLite 离线回放与数据质量报告

### 本次目标

让策略验证不再依赖实时 API。我们需要能用本地 SQLite 中已经保存的市场和价格历史，重复跑同一套回测。

### 已完成

- 新增 CLI 命令：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml replay-backtest --market-type price_target
```

- `replay-backtest` 复用正式 `backtest` 的输出逻辑。
- 新增 `data-quality` 命令：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml data-quality
```

- 输出 `data/data_quality.csv`。

### 本轮离线回放结果

本地 SQLite 样本：

- 市场数：35。
- 有历史价格市场：35。
- 至少 24 个价格点市场：35。
- 价格点总数：5448。

`replay-backtest --market-type price_target`：

- 有交易市场：4。
- 交易数：14。
- 胜率：约 `57.1%`。
- 组合 PnL：约 `+10.25 USDC`。
- 总费用：约 `5.89 USDC`。
- 总滑点：约 `0.44 USDC`。
- 逐 bar mark-to-market 最大回撤：约 `1.8%`。

### 当前判断

这是一个正向小样本，但还不能支持实盘。样本数量、时间跨度和市场类型都太少，而且还没有真实盘口深度、Maker 成交概率、部分成交、结算结果校验。

### 下次继续

建议下一步做 Maker 挂单成交概率模型，让 `MAKER` 候选不再只是记录字段，而是能进入更真实的模拟订单生命周期。

## 2026-05-10：Maker 挂单成交模拟

### 本次目标

让 Maker 不再只是纸面上的“更低买入价”，而是进入订单生命周期：创建挂单、等待成交、超时取消。

### 已完成

- Backtest 支持 `MAKER_BUY_YES`。
- Maker 挂单路径：

```text
created -> submitted -> accepted -> matched -> settled
```

- Maker 超时路径：

```text
created -> submitted -> accepted -> canceled
```

- 组合资金曲线已识别 `MAKER_BUY_YES`，避免把 Maker 买入漏算成免费资金。
- 新增测试覆盖 Maker 成交和组合曲线口径。

### 重要发现

启用 Maker 后，第一次本地回放暴露出组合曲线 bug：逐市场 PnL 为负，但组合曲线错误显示大幅盈利。修复后结果变为：

- 交易数：25。
- 胜率：约 `27.8%`。
- 组合 PnL：约 `-52.51 USDC`。
- 逐 bar mark-to-market 最大回撤：约 `7.1%`。

这说明当前 Maker 候选存在明显逆向选择风险：价格跌到我们的挂单价时，往往不是“捡便宜”，而可能是市场继续走弱。

### 当前决策

默认配置改为：

```toml
maker_enabled = false
```

Maker 模型保留用于研究，但不作为默认模拟盘策略。

### 下次继续

建议下一步做盘口深度和外部 BTC 价格源。当前策略只看 Polymarket 自身历史价格，容易把市场内部噪音误判成 edge。

## 2026-05-10：外部 BTC 现货价格源

### 本次目标

接入一个公开 BTC 现货价格源，为后续判断 Polymarket 是否滞后或过度反应做准备。

### 已完成

- 新增 `src/ploymarket_sim/btc_price.py`。
- 新增 CLI 命令：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml btc-price
```

- 输出 `data/btc_price_candles.csv`。
- 当前默认来源：Coinbase public BTC-USD candles。
- 当前默认粒度：`ONE_HOUR`。

### 本轮观察

本轮抓取：

- K 线数量：345。
- 最新 close：约 `80947.94`。

### 当前判断

外部价格源暂时只作为研究数据，不直接进入交易信号。下一步应该做时间对齐，比较 BTC 现货价格变化和 Polymarket YES 价格变化。

## 2026-05-10：信号快照与 BTC/Polymarket 对齐报告

### 本次目标

提升样本验证能力。每轮模拟盘不只输出 CSV，还要写入 SQLite 快照；同时把 Polymarket YES 历史价格和 BTC 现货 K 线对齐，观察未来 1h/3h/6h 的变化。

### 已完成

- SQLite 新增 `paper_snapshots` 表。
- `paper-run` 会保存每轮信号和执行计划快照。
- 新增 `src/ploymarket_sim/alignment.py`。
- 新增 CLI 命令：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml alignment-report --market-type price_target
```

- 输出：
  - `data/alignment_report.csv`
  - `data/alignment_summary.csv`

### 本轮结果

SQLite 当前状态：

- 市场数：35。
- 价格点：5448。
- paper snapshots：35。

对齐报告：

- `1h`: 5377 条，平均 YES 变化约 `-0.0005`，平均 BTC 收益约 `0.0321%`。
- `3h`: 5307 条，平均 YES 变化约 `-0.0011`，平均 BTC 收益约 `0.0605%`。
- `6h`: 5202 条，平均 YES 变化约 `-0.0021`，平均 BTC 收益约 `0.0986%`。

### 当前判断

整体平均值不能直接用于交易。下一步要按信号动作、市场类型、流动性、YES 价格区间、BTC 涨跌区间分层，寻找是否存在稳定 edge。

## 2026-05-10：第一版 Edge 分层报告

### 本次目标

从整体平均值进入条件分层，观察哪些“当时可见”的条件下，未来 YES 价格表现更好或更差。

### 已完成

- 新增 `src/ploymarket_sim/edge_report.py`。
- 新增 CLI 命令：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml edge-report --min-samples 30
```

- 输出 `data/edge_report.csv`。

### 重要修正

第一版思路里曾考虑按未来 BTC 收益分桶，这会引入未来函数。已改成按“过去 1 小时 BTC 动量”分桶，未来 YES 变化只作为结果。

### 本轮观察

- 分桶数：45。
- 最好桶：`1h / YES 0.20-0.50 / BTC过去1h下跌0.25%-1%`，平均 YES 变化约 `+0.0022`，样本 `99`。
- 最差桶：`6h / YES>=0.50 / BTC过去1h下跌0.25%-1%`，平均 YES 变化约 `-0.0414`，样本 `33`。

### 当前判断

目前还没有强到足以开仓的正向 edge。更明确的信号是：高 YES 价格市场在 BTC 短线走弱后表现很差，适合作为风险过滤器候选。

### 下次继续

建议把这个坏条件先转成策略过滤器：当 YES 价格高于 `0.50` 且 BTC 过去 1 小时下跌超过 `0.25%` 时，不允许做多 YES。然后重新跑离线回放，观察最大回撤和亏损交易是否下降。

## 2026-05-10：BTC 动量坏条件过滤器

### 本次目标

把 edge 分层报告中最明确的坏条件转成保守过滤器，而不是强行寻找开仓条件。

### 已完成

新增配置：

```toml
[btc_filter]
enabled = true
lookback_hours = 1
down_threshold = -0.0025
avoid_yes_price_gte = 0.50
```

规则：如果当前 YES 价格高于或等于 `0.50`，且 BTC 过去 1 小时跌幅超过 `0.25%`，则跳过做多 YES。

### 本轮离线回放结果

对比过滤前：

- 交易数：`14 -> 12`。
- 胜率：约 `57.1% -> 66.7%`。
- 组合 PnL：约 `+10.25 -> +17.74 USDC`。
- 逐 bar 最大回撤：约 `1.8% -> 1.2%`。

### 当前判断

这是一个方向正确的小改进：先减少坏交易，而不是追求更多交易。但样本仍然太小，必须进入长期模拟盘验证。

## 2026-05-10：每日复盘报告

### 本次目标

为长期模拟盘建立每日健康检查，不再靠人工翻 CSV 判断是否接近实盘。

### 已完成

- 新增 `src/ploymarket_sim/daily_report.py`。
- 新增 CLI 命令：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml daily-report
```

- 输出 `data/daily_report.csv`。

### 当前日报

当前状态：

```text
readiness = not_ready
```

原因：

- paper-run 样本只有 `3` 轮。
- 离线回放交易数只有 `12`。
- 虽然当前回放 PnL 为正，最大回撤约 `1.2%`，但样本远远不足。

### 下次继续

建议开始长期模拟盘采样流程：让 `paper-loop` 以固定频率运行，并每天生成 `paper-report`、`alignment-report`、`edge-report` 和 `daily-report`。

## 2026-05-10：一键研究流水线

### 本次目标

把每天需要手动执行的一串命令收束成一个脚本，方便长期模拟盘采样。

### 已完成

新增脚本：

```bash
scripts/research_cycle.sh
```

它会依次运行：

- `paper-run`
- `paper-report`
- `btc-price`
- `alignment-report`
- `edge-report`
- `replay-backtest`
- `data-quality`
- `daily-report`

### 当前状态

本轮运行后：

- paper-run 轮数：5。
- 离线回放交易数：12。
- 回放 PnL：约 `+17.74 USDC`。
- 逐 bar 最大回撤：约 `1.2%`。
- readiness：`not_ready`。

原因仍是样本不足。

## 2026-05-10：macOS 定时运行脚本

### 本次目标

让研究流水线可以在本机后台定时运行，持续积累 paper-run 样本。

### 已完成

新增：

```bash
scripts/install_research_cycle_launchd.sh
scripts/uninstall_research_cycle_launchd.sh
```

默认每 30 分钟运行一次：

```bash
scripts/install_research_cycle_launchd.sh
```

每 15 分钟运行一次：

```bash
scripts/install_research_cycle_launchd.sh 900
```

停止：

```bash
scripts/uninstall_research_cycle_launchd.sh
```

日志：

```text
logs/research_cycle.out.log
logs/research_cycle.err.log
```

### 当前建议

先用 30 分钟间隔运行 1-2 天，确认没有错误和 API 卡顿，再决定是否提高频率。

## 2026-05-20：从单边 BUY_YES 转向 YES/NO 双边价差扫描

### 本次目标

当前 BUY_YES 动量策略在 5 分钟粒度下回放 PnL 明显为负，因此不继续围绕旧策略微调。根据 Polymarket YES/NO 互补 token 机制，新增只读价差扫描，观察是否存在扣除费用和滑点后仍为正的完整组合机会。

### 已完成

新增：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml spread-scan --market-type price_target
```

输出：

```text
data/spread_scan.csv
```

扫描逻辑：

- `BUY_BOTH`: 同时买入 1 YES + 1 NO，要求 `YES ask + NO ask + 费用 + 滑点 < 1`。
- `SELL_BOTH`: 已持有完整组合时，要求 `YES bid + NO bid - 费用 - 滑点 > 1`。
- 当前只读，不下单，不做实盘。

### 本轮观察

- 扫描 price_target 市场：`22` 个。
- `BUY_BOTH`: `0`。
- `SELL_BOTH`: `0`。
- 最好的 buy edge 约 `-0.0036`，仍为负。
- 结论：方向是正确的，但当前盘口暂未出现扣费后可执行的完整组合套利机会。

### 下一步

继续让定时流水线记录 `spread_scan.csv` 和 `daily_report.csv` 中的价差字段。如果连续多轮出现正 edge，再加入模拟盘状态机：记录机会出现时间、可成交深度、是否在下一轮消失、以及假设成交后的退出/merge/redeem 路径。

## 2026-05-20：补读 X 原文并修正手续费模型

### 本次目标

通过浏览器读取 Ryan Chi 的 X 长文，提取对当前 BTC 双边价差策略最关键的机制细节。

### 新增理解

- `C * feeRate * p * (1-p)` 中的 `C` 是 shares 数量，不是 USDC notional。
- 双边价差不能只看 `YES ask + NO ask < 1`，还要扣除按 shares 计算的 taker fee、滑点，以及机会消失延迟。
- 做完整组合套利时，理想路径是买入 YES+NO 后通过 Merge/Redeem 回到 1 USDC，而不是依赖下一次盘口卖出。
- Maker 在 Polymarket 机制里有手续费和速度优势，但承担被信息流打穿的逆向选择风险。

### 已修正

- 修正本地费用模型：回测使用 USDC notional 时，先等价换算成 shares 口径估算费用。
- `spread-scan` 按 1 YES + 1 NO 的完整组合份额计算费用，避免低估套利成本。

### 交易结论

这次修正会让回测和价差扫描更保守，PnL 可能更难看，但更接近真实交易成本。我们宁愿晚一点进入实盘，也不能依赖低估费用得到的虚假正 PnL。

## 2026-05-20：聚焦 BTC，拆分单日目标市场

### 本次目标

继续聚焦 BTC，不扩散到体育/比赛市场。先把 BTC 市场内部拆细，避免把长期目标、单日目标、日内区间混在一个 PnL 里。

### 已完成

- 新增市场类型：`price_target_daily`。
- 新增命令：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml market-type-report
```

- 输出：`data/market_type_report.csv`。
- 定时流水线已加入 `market-type-report`。

### 本轮观察

- `price_target`: 市场 `35` 个，交易 `8` 笔，PnL 约 `-17.41`。
- `price_target_daily`: 市场 `15` 个，交易 `0` 笔，PnL `0`。
- `price_range_daily`: 市场 `11` 个，交易 `0` 笔，PnL `0`。

### 结论

旧 BUY_YES 动量策略主要在长期 `price_target` 上亏损，对单日/短周期 BTC 市场几乎完全不触发交易。下一步不能继续套旧参数，而应该为 `price_target_daily` / `price_range_daily` 单独设计边界型策略，例如临近 strike、临近结算、BTC 现货短线接近目标价时的盘口滞后。

## 2026-05-21：扩大 BTC 模拟观察面

### 问题

虽然系统已经使用 5 分钟价格历史，但主流水线仍主要对 `price_target` 运行 `backtest`、`paper-run`、`spread-scan`、`alignment-report` 和 `strategy-sweep`。这导致短周期 BTC 市场虽然被存储和分类，却没有进入主回测/模拟盘信号闭环。

### 已调整

`scripts/research_cycle.sh` 改为对 `all` BTC 市场类型运行主观察命令：

- `backtest --market-type all`
- `paper-run --market-type all`
- `spread-scan --market-type all`
- `alignment-report --market-type all`
- `strategy-sweep --market-type all`

### 判断

交易数少的主要原因不是“5 分钟不够细”，而是：

- 旧策略窗口是 6h/24h 均线，天然不适合 5m/15m 边界市场。
- 旧策略只会买 YES，不会围绕临近 strike 的 YES/NO 边界变化做决策。
- 短周期市场已经有样本，但旧规则几乎完全不触发交易。

下一步应优先做 BTC 边界型策略，而不是立刻扩展到 1 分钟。15 分钟可以作为更稳的研究窗口，1 分钟要等数据和执行状态机更成熟后再加。

## 2026-05-21：修正 5 分钟策略窗口

### 问题

默认配置虽然已经抓取 5 分钟 Polymarket/BTC 数据，但信号仍使用 `short_window=72`、`long_window=288`，等价于 6 小时 vs 24 小时均线。这个窗口太慢，不适合 5 分钟/15 分钟 BTC 边界市场，导致模拟盘长期只是在用慢信号空转。

### 已调整

- 默认信号窗口改为 `short_window=6`、`long_window=24`，即 30 分钟 vs 2 小时。
- `min_momentum` 从 `0.015` 降到 `0.005`。
- `min_edge` 从 `0.025` 降到 `0.003`。
- `safety_margin` 从 `0.01` 降到 `0.005`，仅用于模拟盘探索，实盘前必须重新收紧。
- `strategy-sweep` 新增 15 分钟/1 小时、30 分钟/2 小时、1 小时/4 小时、2 小时/8 小时等短周期候选。

### 判断

这不是实盘信号，只是让系统停止用明显错配的慢窗口。接下来要看交易数是否明显增加、PnL 是否改善，以及短窗口是否只是制造更多噪音亏损。

### 第一轮验证后的修正

- `6/24` 全市场回测交易数升至 `46`，但 PnL 恶化到约 `-88.44`。
- 亏损主要来自不同市场类型混用同一个 BUY_YES 动量策略。
- 分市场 sweep 显示 `price_range_daily` 用 `36/144`、`min_momentum=0.0025`、`min_edge=0.0015` 时，交易 `38` 笔、胜率 `57.9%`、PnL 约 `-6.09`，明显优于全市场混跑。
- 因此新增市场类型策略 profile：`price_range_daily` 单独使用 `36/144`，`price_target` 使用更短但更严格的 `6/24`，`company_treasury`、`indirect_event`、`unknown` 暂时只观察不交易。

## 2026-05-21：区分实时行情和研究缓存

### 问题

HTTP cache 默认 TTL 是 `900` 秒，适合减少研究阶段 API 抖动，但不适合模拟盘决策。如果 `paper-run` 读取缓存或优先使用 SQLite 历史，会导致信号和真实盘口存在时间差，尤其不适合 5 分钟市场。

### 已调整

- `paper-run` 每轮优先实时刷新活跃 BTC 市场，发现失败才回退本地市场缓存。
- `paper-run` 每个市场优先实时拉取 Polymarket `prices-history`，失败才回退 SQLite 历史。
- `btc-price` 强制实时拉取 Coinbase candles。
- `discover`、`signals`、`backtest`、`spread-scan` 默认绕过 HTTP cache。
- `/book` 盘口原本就没有使用 HTTP cache，仍保持实时请求。

### 当前策略有效点

- 交易次数已经从个位数提升到约 `28` 笔，开始具备初步评估价值。
- `price_range_daily` 是当前最有效的市场类型，最新回放约 `24` 笔、胜率约 `58%`、PnL 小幅为正。
- 将 `company_treasury`、`indirect_event` 排除出交易后，整体 PnL 明显改善。

### 当前策略无效点

- 样本数仍不足，不能证明稳定盈利。
- 实时 paper-run 仍没有触发可执行交易，说明当前价格区间经常太极端，不能为了交易次数硬追。
- `price_target` 样本太少，对总 PnL 的贡献暂时不可靠。
- 策略仍主要是 BUY_YES 动量逻辑，还没有真正建成 BTC 边界/strike 距离模型。

## 2026-05-21：加入 BTC strike 边界过滤

### 观察

样本扩展到约 `42` 笔后，整体 PnL 回到小幅负值。主要亏损集中在 `price_range_daily` 的较高 strike，例如 `above $78,000`，说明单纯看 Polymarket YES 动量会在 BTC 现货尚未接近 strike 时过早买入。

### 已尝试

- 对 `price_range_daily` 解析问题中的美元 strike。
- `above strike` 市场：BTC 现货未接近或站上 strike 时，不允许 BUY_YES。
- `below strike` 市场：BTC 现货未接近或跌破 strike 时，不允许 BUY_YES。
- 回测和 paper-run 使用同一套 strike 过滤，避免回测和模拟盘规则不一致。

### 判断

第一版 strike 过滤过于粗糙，回测 PnL 从约 `-3.45` 恶化到约 `-27.84`。它会挡掉一些后续修复/反弹交易，所以不能作为默认执行规则。随后尝试把 `price_range_daily` 的 `min_edge` 提高到 `0.005`，交易数从约 `42` 降到 `36`，但 PnL 仍恶化到约 `-22.98`。结论：当前亏损不是简单靠减少交易次数能解决，默认参数恢复为 `min_edge=0.0015`，下一步应做更结构化的 BTC 方向/入场时机模型。

## 2026-05-21：修正 BTC candles 覆盖不足

### 问题

`btc-price` 每轮只保存 Coinbase 最近一批 5 分钟 candles，并覆盖旧 CSV。这会导致 1 周 Polymarket 历史回测里很多入场点没有 BTC 现货上下文，进而让 strike/距离类模型缺数据。

### 已调整

- `btc-price` 新增 merge 逻辑：新拉到的 candles 与已有 `data/btc_price_candles.csv` 按 timestamp 合并。
- 新数据覆盖同 timestamp 的旧数据，但不会删除更早历史。
- 这为后续 BTC spot vs strike 距离模型打基础。

## 2026-05-22：按 strike 验证高确定性事件假设

### 观察

昨晚 BTC 大部分时间在 `78k` 下方波动。回测显示 `above $74k` 和 `above $76k` 贡献正 PnL，而 `above $78k` 是主要亏损来源。

### 已调整

- 新增 `strike-report` 命令。
- 输出 `data/strike_report.csv`，按 `price_range_daily` 的美元 strike 汇总交易数、胜率、PnL、手续费和滑点。
- 定时流水线加入 `strike-report`。

### 判断

“多做高确定性 above 事件”方向合理，但不能只看确定性。高确定性事件通常 YES 价格很高，剩余收益很薄，必须同时满足扣除手续费、滑点、盘口深度和尾部风险后的正期望。下一步用 strike 分层报告寻找可泛化过滤规则。

## 2026-05-22：加入资金流与大额钱包观察层

### 观察

`above $78k` 不是永远不能做，真正的问题是 BTC 现货没有有效突破时，单纯 BUY_YES 动量会反复买在错误位置。同理，`under $60k` 这种远低于现货的市场也不能因为 YES 便宜就持续买入。`above` 和 `under/below` 都应该统一看“strike 距离现货多远、最近资金流支持哪一边”。

### 已调整

- 市场发现新增保存 Polymarket `conditionId`，用于按市场查询交易流。
- 新增 `flow-scan` 命令，输出 `data/flow_scan.csv`。
- `flow-scan` 会按市场统计最近交易的 `BUY/SELL + YES/NO`、大额交易数、活跃钱包数、最大成交钱包、YES/NO 净资金压力。
- 新增 `strike_direction`、`strike_distance_pct`、`strike_risk` 字段，统一标记 `far_above_spot`、`far_below_spot`、`near_spot` 等风险。
- 定时研究流水线加入 `flow-scan`，但暂时只观察，不直接改变交易动作。

### 判断

资金流只能作为辅助确认，不能直接等同于“聪明钱”。大额钱包可能在做对冲、套利、拆单或库存调整，也可能只是错了。下一步应把 `flow_signal` 与历史回测结果关联：例如 `near_spot + YES_PRESSURE` 是否改善 `above` 市场表现，`far_above_spot + NO_PRESSURE` 是否能过滤类似 `$78k/$80k` 的亏损入场。

## 2026-05-22：整理动态 strike 执行条件

### 观察

不能把 `$74k`、`$76k`、`$78k` 这类单次行情下表现较好的 strike 写死进策略。行情大幅移动后，同一个 strike 的含义会完全改变。真正有泛化能力的条件应该围绕“当前 BTC 现货与 strike 的相对距离”构建。

### 已调整

- 新增 [BTC 策略执行条件](/Users/pizza_yang/code/ploymarket/docs/strategy/btc-execution-conditions.md)。
- 文档明确 `above` 与 `under/below` 要统一按 strike 距离、资金流、成本和风控判断。
- 更新 Obsidian 首页、docs README、市场分类笔记和当前系统状态，方便下次继续时直接进入策略执行条件。

### 判断

下一步不是继续手工挑某个 strike，而是验证 `near_spot + YES_PRESSURE`、`far_above_spot + NO_PRESSURE`、`far_below_spot + NO_PRESSURE` 等组合是否能稳定改善回测 PnL。只有通过样本验证后，才能进入模拟盘执行层。

## 2026-05-22：加入 BUY_NO 与反转回测实验

### 观察

`above $78k` 的持续亏损不是没有止损，而是旧策略只能 `BUY_YES`。当 BTC 多次突破失败时，正确方向可能不是继续等待更好的 BUY_YES，而是允许 `BUY_NO` 或在止损后研究反向机会。

### 已调整

- 新增 `reversal-backtest` 命令。
- 新增 `data/reversal_summary.csv` 和 `data/reversal_trades.csv` 输出。
- 并排比较 `YES_ONLY`、`YES_NO`、`YES_NO_REVERSAL` 和不同止损宽度。
- `research_cycle.sh` 加入 `reversal-backtest --market-type price_range_daily`。

### 初步结果

当前 `price_range_daily` 样本上：

- `YES_ONLY_SL25`: PnL 约 `-12.91`。
- `YES_NO_SL25`: PnL 约 `+129.10`。
- `YES_NO_REV_SL25_CD60M`: PnL 约 `+108.56`。
- `YES_NO_REV_SL15_CD60M`: PnL 约 `-1.05`。
- `YES_NO_REV_SL12_CD60M`: PnL 约 `-75.07`。

### 判断

允许 `BUY_NO` 是目前最有希望的方向之一，但收紧止损没有自动改善结果。`12%/15%` 止损会显著增加噪音交易和手续费消耗。止损后反转也必须重新满足反向净 edge，不能无脑反手。下一步应该把 `BUY_NO` 与动态 strike、资金流 `NO_PRESSURE` 结合验证，防止当前结果只是单日样本过拟合。

## 2026-05-22：将 BUY_NO 升级为主候选策略

### 观察

单独的 `reversal-backtest` 已经证明，在当前 `price_range_daily` 样本里，允许 `BUY_NO` 比只做 `BUY_YES` 更有希望。原因很直观：当某个 above strike 多次突破失败时，旧策略只能“不买”或反复买 YES；新策略至少可以在 YES 动量转弱且 NO 扣除成本后仍有正 edge 时，选择买 NO。

### 已调整

- `signals` 支持在 `price_range_daily` 市场生成 `BUY_NO`。
- `execution` 支持把 `BUY_NO` 作为 taker 候选，limit price 使用 `1 - yes_price`。
- `backtest`、`portfolio` 和订单事件支持 `BUY_NO` / `SELL_NO` 的入场、止损、止盈、期末平仓和 mark-to-market。
- `paper-run`、`paper-report` 和 CLI 摘要新增 `buy_no` / `buy_no_count` 统计。
- 价格过滤改成按交易侧判断：买 YES 看 YES 是否太贵或太便宜；买 NO 看 NO 是否太贵或太便宜。

### 最新验证

主回测接入 `BUY_NO` 后，`price_range_daily` 当前样本约 `88` 笔交易、胜率约 `79.5%`、PnL 约 `+127`；全部 BTC 市场约 `110` 笔交易、胜率约 `72.7%`、PnL 约 `+108`、最大回撤约 `5.0%`。

同一轮 `paper-run` 没有强行给出实时交易候选：`buy_yes=0`、`buy_no=0`、`skip=33`。这反而是好现象，说明策略接入后没有为了交易而交易。

### 判断

`BUY_NO` 可以进入候选策略池，但还不能实盘。下一步重点是继续扩大样本，观察真实 paper-run 是否能持续出现高质量 `BUY_NO`，并把资金流 `NO_PRESSURE`、动态 strike 距离和冷却规则加入分层验证。我们要追求的是稳定正期望，而不是在某一晚样本里刚好赚到钱。

## 2026-05-22：加入 BTC regime 过滤

### 观察

当前样本里 BTC 大部分时间处于 `78k` 下方震荡，`BUY_NO above 78k` 自然容易表现更好。但这不代表 `BUY_NO` 在单边上涨里也安全；同理，`BUY_YES` 在持续下跌里也会反复亏损。因此不能只用当前震荡行情验证策略，必须先识别 BTC 现货处于趋势还是震荡。

### 已调整

- 新增 `btc_regime` 模块，按 BTC 过去 `15m`、`1h`、`3h` 收益和 `1h` 高低区间识别 `uptrend`、`downtrend`、`range_bound`、`volatile`、`neutral`。
- 在 `backtest` 和 `paper-run` 中接入统一方向过滤。
- `above` 市场：震荡且 BTC 仍在 strike 下方时，不追 `BUY_YES`；上涨趋势接近或站上 strike 时，不做 `BUY_NO`。
- `below/under` 市场：规则反向处理，避免在明显下跌并接近/跌破 strike 时继续做 `BUY_NO`。
- 修正旧 BTC 下跌过滤器：它现在只阻止 `BUY_YES`，不再误伤 BTC 下跌时合理的 `BUY_NO`。

### 最新验证

加入 regime 过滤后，主回测从约 `110` 笔降到 `108` 笔，全部 BTC 市场 PnL 从约 `+110` 降到约 `+101.8`；`price_range_daily` 从约 `88` 笔降到 `86` 笔，PnL 从约 `+127` 降到约 `+118.7`，最大回撤仍约 `5.0%`。

### 判断

短期 PnL 稍微下降是可以接受的，因为过滤器的目标不是过拟合当前震荡，而是减少未来单边行情里的反向交易风险。下一步要把 regime 分层写进报告：分别统计 `uptrend/downtrend/range_bound` 下 `BUY_YES` 和 `BUY_NO` 的胜率、PnL、最大回撤，确认过滤器不是凭感觉挡交易。

## 2026-05-22：禁止用本地缓存作为实时交易依据

### 观察

`IncompleteRead` 多半是网络/API 传输不稳定，`orderbook 404` 多半是市场或 token 已经过期、下架或订单簿不可用。此前系统为了保证研究流水线不断，会在 `paper-run` 和 `spread-scan` 降级到本地 SQLite 市场和历史；这适合回测和研究连续性，但不适合作为实盘或实时模拟候选。

### 已调整

- `paper-run` 现在必须使用 live market discovery 和 live `prices-history`；如果实时数据不可用，本轮写出空扫描，不再用 SQLite 历史补位。
- `spread-scan` 现在必须使用 live market discovery；如果实时发现不健康，本轮输出 `data_degraded`，不再扫描本地旧市场。
- CLOB orderbook 返回 `404` 时，会把 YES/NO token 写入 `stale_tokens`，后续一段时间跳过，避免每轮重复扫失效订单簿。
- `paper-report` 会把空 `paper_run_*.csv` 记录为 `DATA_DEGRADED`。
- `daily-report` 如果最新 paper-run 没有实时市场，会保持 `not_ready`，理由明确为“禁止把本地缓存当作实盘依据”。

### 判断

这会让网络不稳定时的 paper-run 市场数变少，甚至为 0，但这是正确行为。回测可以用本地缓存，实盘候选必须依赖实时数据。宁愿少交易，也不能用过期数据产生看似漂亮但不可执行的信号。

## 2026-05-23：修复实时发现抖动导致样本骤降

### 观察

本地网络到 Polymarket/Gamma API 仍频繁出现 `IncompleteRead`。在一次复现中，实时发现只有 `live=1`，而 SQLite 历史市场有 `118` 个；如果完全禁用回退，模拟盘市场数会骤降，难以验证策略。但如果直接使用全部本地缓存，又会把过期市场当作实盘候选。

### 已调整

- Gamma `/markets` 分页请求从每页 `20` 缩小到最多 `10`，减少大响应中断概率。
- 单个 market page 失败不再立刻终止全部发现，连续失败多页后才停止。
- SQLite 新增按 `observed_at` 读取“最近 live 观察过的市场”的能力。
- `paper-run` / `spread-scan` 在 live discovery 不健康时，只允许回退到最近 `fresh_market_ttl_seconds=900` 秒内 live 观察过的市场池。
- `paper-run` 的 CLOB `prices-history` 仍必须实时拉取；`spread-scan` 的订单簿仍必须实时拉取，不用旧价格或旧盘口补位。

### 最新验证

一次实测中，live discovery 降级为 `live=5 local=118`，但新鲜 live 缓存恢复出 `fresh=40` 个候选市场；最终 `paper-run` 因部分 CLOB `prices-history` 仍有 `IncompleteRead`，实际记录 `markets=30`、`buy_yes=0`、`buy_no=0`、`skip=30`。`spread-scan` 在 `live=1` 时使用 `fresh=5` 个新鲜 live 市场继续扫描真实订单簿，输出 `markets=5`。

### 判断

这一步解决的是“市场发现层因为网络抖动把样本砍没”的问题，同时没有放松实盘安全边界。下一个瓶颈转移到 CLOB `prices-history` 的稳定性：需要继续优化历史拉取重试、降采样或分批请求，否则部分市场仍会被跳过。

## 2026-05-23：加入模拟持仓状态和同市场冷却

### 观察

实时 paper-run 连续多轮把候选集中在 `BUY_NO above 76k`。这与 BTC 长时间在 76k 下方有关，但如果每轮都当成一次新交易，会高估真实可执行交易次数。真实账户里，同一市场已经开仓后不应该每 5-10 分钟重复买入。

### 已调整

- SQLite 新增 `paper_positions`，记录模拟盘同一市场的持仓方向、入场价、份额、成本、开仓时间、状态和冷却时间。
- `paper-run` 遇到已有 open position 时，输出 `HOLD/SKIP`，原因写明“已有模拟持仓，不重复开同一市场”。
- 模拟持仓达到旧版止盈或止损后，会关闭状态，并进入 `paper_reentry_cooldown_seconds=3600` 秒同市场冷却；后续已升级为分批止盈和止盈短冷却。
- `BUY_NO above` 增加突破风险保护：BTC 接近或站上 strike 时暂停逆突破方向；`below/under` 规则反向处理。

### 验证

第一轮运行记录 `2277981 BUY_NO TAKER`，第二轮同一市场变为 `HOLD/SKIP`，原因是 `已有模拟持仓 NO，不重复开同一市场`。这说明模拟盘已经从“重复信号扫描”向“有持仓状态的模拟账户”前进了一步。

## 2026-05-23：加入分批止盈和移动止盈

### 观察

`BUY_NO above 76k` 这类仓位在 BTC 持续低于 strike 时可以较快出现 `10%-15%` 浮盈，但旧规则要求达到 `35%` 才止盈，导致利润长时间停留在账面上。对于 5 分钟/短周期市场，这个阈值偏高，容易把本来可以落袋的小收益回吐掉。

### 已调整

- `take_profit_pct` 从 `35%` 降到 `25%`，作为全量止盈。
- 新增 `partial_take_profit_pct=12.5%` 和 `partial_take_profit_fraction=50%`：先卖出一半，剩余仓位继续跟踪。
- 新增移动止盈：浮盈达到 `12%` 后，如果从峰值回吐 `6%`，卖出剩余仓位。
- 止盈后的同市场冷却缩短为 `600` 秒；止损仍保持 `3600` 秒，避免止损后马上在同一错误方向反复进场。
- SQLite `paper_positions` 增加 `peak_price` 和 `partial_take_profit_count`，避免同一仓位每轮重复触发分批止盈。

### 判断

这一步把模拟盘从“有信号、有持仓”推进到“有仓位管理”。后续复盘不能只看是否开仓，还要看分批止盈是否提高已实现 PnL、是否降低回撤，以及短冷却后重新开仓是否真的增加正期望，而不是增加噪音交易。

## 2026-05-23：拆分回测止盈和模拟盘止盈

### 观察

对照实验显示，主回测 PnL 从 `100+` 降低的主要原因不是 BTC regime 过滤，而是把全量止盈从 `35%` 降到 `25%` 后，过早卖掉了一批历史上贡献主要利润的赢家。在本地 price_range_daily 样本里，`25%` 止盈约 `+75`，恢复 `35%` 后约 `+145`。

### 已调整

- `take_profit_pct` 恢复为 `35%`，用于主回测/策略退出。
- 新增 `paper_full_take_profit_pct=25%`，只用于实时模拟盘保护性全量止盈。
- 保留 `12.5%` 分批止盈，继续把部分利润落袋。
- 新增 `paper_reentry_edge_multiplier=2.0`：止盈后同市场重新开仓必须达到普通 edge 门槛的两倍，避免频繁止盈后追进导致手续费变多。

### 判断

这次修复的核心是“不要让模拟盘保护逻辑污染历史回测主策略”。我们仍然要保留落袋为安，但不能牺牲已经验证过的趋势段收益。

## 2026-05-23：启动 Kalshi 数据适配器和双平台匹配

### 观察

Kalshi 也有 BTC 事件合约，且公开市场数据 API 可以不认证读取。官方文档说明公开 Market Data endpoint 使用 `https://external-api.kalshi.com/trade-api/v2`，`GET /markets` 可分页获取市场，`GET /markets/{ticker}/orderbook` 可读取订单簿。第一阶段我们只做数据研究，不接账号、不签名、不下单。

### 已调整

- 新增 `kalshi.py`：读取 Kalshi BTC 相关公开市场，支持 `KXBTC`、`KXBTCD`、`KXBTC15M`、`KXBTCMAX150` 系列。
- 新增 `cross_platform.py`：把 Polymarket 和 Kalshi 市场归一化为统一结构：平台、市场 ID、问题、strike、方向、日期、YES/NO 价格、流动性。
- CLI 新增 `kalshi-discover`：打印 Kalshi BTC 市场快照。
- CLI 新增 `cross-platform-report`：输出 `data/cross_platform_matches.csv`，按 strike、方向和日期匹配两个平台的相似 BTC 合约。
- 匹配逻辑默认保守：方向为 `unknown` 的市场不匹配，日期优先从问题文本提取，避免把 range bucket 或不同日期的合约误认为同一事件。

### 最新验证

本地可以拉到 Kalshi `KXBTC15M`、`KXBTCMAX150`，并在网络较好时拉到 `KXBTC/KXBTCD` 的当前 BTC 分段市场。`cross-platform-report` 能生成匹配 CSV；但本地到 Kalshi 也会偶发 `IncompleteRead` / remote close，说明 VPS 数据层仍然有价值。

### 下一步

当前只是跨平台快照匹配，还不是 Kalshi 历史回测。真正的双平台回测需要继续补：

- Kalshi 历史价格/订单簿数据采集。
- Kalshi 费用模型。
- 同一事件的结算规则校验，尤其 Polymarket 和 Kalshi 的 BTC 价格源、时间窗口和结算时区可能不同。
- 跨平台路由回测：同一信号只选择净 edge 更高、盘口更深的平台，而不是简单双倍下注。

## 2026-05-24：修复 price_target 远离 strike 仍反复入场

### 观察

`Will Bitcoin reach $80,000 May 18-24?` 在 BTC 仍距离 80k 较远时出现多次 BUY_YES，并连续止损。`Will Bitcoin dip to $74,000 May 18-24?` 初期更接近 strike，入场逻辑相对能理解，但后续受宏观消息反转影响，也出现止损后重复进场风险。

根因不是简单的止损参数，而是 `price_target` 复用了普通 YES 动量逻辑，没有强制检查 BTC 现货距离，也没有针对 target 市场设置足够长的止损后冷却。更糟的是，当 BTC 现货数据缺失时，旧逻辑会默认放行。

### 已调整

- `price_target` / `price_target_daily` 入场前必须能识别 strike 和方向。
- `dip/drop/fall to` 现在会被识别为 below 方向，而不是 unknown。
- `price_target` / `price_target_daily` 入场前必须有 BTC 现货确认；没有现货上下文时拒绝交易。
- target 市场默认只允许距离 strike `2.5%` 内的 BUY_YES 候选，远端 reach/dip 只观察。
- target 市场如果方向与 BTC regime 明显相反，例如 above 遇到 downtrend、dip/below 遇到 uptrend，会拒绝追 YES。
- target 市场止损后同方向冷却 `21600` 秒，避免连续在同一周内目标上反复亏损。

### 验证

本地 replay 结果：

- 全市场 PnL 从上一轮约 `+67.84` 提升到 `+163.61`。
- `price_target` 从约 `-73.45` 收窄到 `-2.94`。
- `Will Bitcoin reach $80,000 May 18-24?` 从多次重复交易缩到 1 次完整交易，PnL 约 `-8.54`；大量远离 strike 或缺少 BTC 现货确认的信号被拒绝。
- `Will Bitcoin dip to $74,000 May 18-24?` 从明显亏损收敛到约 `+0.75`，保留了临近 strike 的机会，同时减少无现货确认和止损后重复入场。
- 最新 daily report：`readiness=candidate`，`trades=156`，`pnl=163.61`，MTM 最大回撤 `5.8%`。

### 判断

这是一次有效修复，但仍不能直接实盘。当前结果说明“动态现货距离 + 缺数据拒绝 + target 冷却”明显优于只看 Polymarket YES 动量。下一步需要继续观察 paper-run 是否也能在实时环境下稳定遵守这些拒绝规则，并重点看网络数据缺失是否会让可交易样本过少。

## 2026-05-24：把 price_target 扩展到 BUY_NO 候选

### 观察

`price_target` 如果只做 BUY_YES，会错过 `reach 80k` 这种远端目标失败时的 NO 收益。但直接给所有 target 打开 BUY_NO 会恶化结果：`dip to 74k` 的 NO 价格一度接近 `0.80`，赔率太薄，消息反转时容易一次亏掉多轮小收益。

### 已调整

- 主信号层允许 `price_target` / `price_target_daily` 在 YES 动量转弱、NO 扣除成本后仍有净 edge 时产生 `BUY_NO`。
- target `BUY_NO` 复用现货距离过滤：above/reach 市场接近或站上 strike 时不做 NO；below/dip 市场接近或跌破 strike 时不做 NO。
- target `BUY_NO` 增加趋势过滤：above/reach 遇到 BTC uptrend 不逆势做 NO；below/dip 遇到 BTC downtrend 不逆势做 NO。
- target 增加赔率过滤：`BUY_YES` 价格默认不高于 `0.65`，`BUY_NO` 的 NO 价格默认不高于 `0.75`。

### 验证

本地 replay 结果：

- 第一版直接打开 target BUY_NO 后，全市场 PnL 降到约 `+149.23`，`price_target` 降到约 `-17.06`，说明不能无差别启用。
- 加入 target 赔率过滤后，全市场 PnL 提升到 `+166.51`，`price_target` 从上一稳定版约 `-2.94` 改善到 `+0.21`。
- `Will Bitcoin reach $80,000 May 18-24?` 通过 `BUY_NO` 获利约 `+8.36`。
- `Will Bitcoin dip to $74,000 May 18-24?` 中高价 NO / 高价 YES 被拦截，避免了第一版新增 BUY_NO 后的主要亏损。

### 判断

`price_target` 可以加入 BUY_NO，但必须是“失败突破/远离目标 + 合理 NO 价格 + 不逆 BTC regime”的候选，而不是所有 YES 下跌都买 NO。当前只把 BUY_NO 纳入主策略，真正的“止损后自动反转”还需要继续单独做更严格的回测，不能直接并入模拟盘。

## 2026-05-25：迁移到 VPS 独立前瞻样本

### 部署

- VPS 已用于实时公开行情抓取、回测与 paper-run，不安装钱包、不存放私钥、不提供实盘下单能力。
- 新增 `scripts/setup_vps_runtime.sh`，服务器输出写到 `runtime/data/`，缓存写到 `runtime/cache/http/`，与仓库原有 `data/` 研究结果隔离。
- 新增 `scripts/install_research_cycle_cron.sh`，在 VPS 上每 10 分钟尝试执行一次完整研究周期；完整周期约需 `274` 秒，且脚本锁会避免重叠。
- VPS 到 Coinbase、Gamma 与 CLOB 公共接口的初步请求耗时约 `0.05-0.07` 秒，首轮错误日志为空，暂未看到本地曾出现的 `IncompleteRead`。

### 第一轮干净样本

- 覆盖实时市场 `49` 个；paper-run 首轮仅有 `1` 个 `TAKER` 候选，尚无足够连续样本。
- 回放成交 `70` 笔，胜率 `45.7%`，PnL `-35.60`，费用 `42.12`，滑点 `2.19`，MTM 最大回撤 `8.0%`。
- 交易只来自 `price_range_daily`；`price_target` 本轮被过滤为零成交。
- strike 维度中，`76000` 贡献约 `+22.18`，`78000` 拖累约 `-46.91`，说明临近震荡/突破失败市场仍是当前主要风险源。
- readiness 为 `not_ready`，原因不仅是 paper-run 样本不足，新独立样本的净结果本身也为负。

### 判断

旧目录上的正 PnL 只能作为历史研究参考，不能覆盖 VPS 前瞻样本的负结果。后续优化重点应放在 `78000` 附近重复入场、方向确认与费用侵蚀上，继续积累新样本并做受控对照；在新样本未稳定转正且风险可解释前，不进入实盘。

## 2026-05-25：修复 VPS 首轮 78k 亏损根因

### 根因分析

- `BUY_NO` 实际已经在运行，首轮 `78k` 亏损不是因为只做了 YES；两个日结 `78k` 市场合计有多次 YES/NO 来回入场。
- 干净 VPS 初始只有从 `2026-05-24 08:15 UTC` 开始的 Coinbase 五分钟 K 线，但导致主要亏损的入场从 `2026-05-20` 就已发生。旧回测在缺少对应 BTC 现货确认时仍允许 `price_range_daily` 方向入场，产生不可验证的亏损交易。
- 回测只对 target 市场执行止损后冷却，而 paper-run 已经对普通日结市场执行冷却；这一不一致使回测中同一 `78k` 市场可以止损后数分钟内立即反向或重新入场，在震荡期持续消耗费用。
- 本地总 PnL 看似更好，是因为汇总了更多历史市场；其最新 May 26 `above 78k` 单市场本身同样已经出现明显亏损，不能据此证明最新环境更差。

### 已调整

- `price_range_daily` 的方向性入场现在必须有同时间段 BTC 现货确认；没有对应 K 线时，`BUY_YES` 与 `BUY_NO` 都拒绝进入回放结果。
- 对 `above` 日结市场，BTC 尚未接近 strike 时暂停 `BUY_YES`，但保留在有现货确认前提下研究 `BUY_NO` 的空间。
- 主回测在普通日结市场止损后也执行同市场冷却，与 paper-run 行为一致，避免震荡中立即反手。

### VPS 对照验证

- 修复前同一隔离运行目录：交易 `70` 笔，胜率 `45.7%`，PnL 约 `-34.30` 至 `-35.60`，MTM 最大回撤 `8.0%`；`78k` strike 拖累约 `-45.64` 至 `-46.91`。
- 修复后同一批实时市场：交易 `10` 笔，胜率 `60.0%`，PnL `+2.10`，费用 `3.28`，滑点 `0.31`，MTM 最大回撤 `1.5%`；`78k` strike 收敛为约 `-0.59`。
- 修复后保留的两个 `78k` 有效入场均为 `BUY_NO`：May 25 约 `+2.45`，May 26 约 `-3.04`。这说明 NO 方向有价值，但“BTC 低于 strike”并不足以保证单次 NO 盈利。

### 判断

这次变化主要消除了不可验证样本与无冷却重复交易，不应被解读为策略已经转为稳定盈利。当前有效交易仅 `10` 笔，且 `readiness=not_ready`；下一步必须继续在 VPS 积累有完整 BTC 对齐背景的新样本，再判断 `BUY_NO` 的定价过滤、趋势过滤和止盈机制是否需要调整。

## 2026-05-25：VPS 实时候选链关闭缓存并按订单簿成交

### 审计发现

- `paper-run` 的市场发现和 CLOB 价格历史原本已经直接请求 live API，`spread-scan` 的订单簿和 `flow-scan` 的成交流也未使用 HTTP cache。
- 但 VPS 配置仍允许 HTTP stale cache，并允许市场发现降级时使用最近观察过的市场池；这不适合作为接近实盘的模拟开仓依据。
- 更重要的是，旧 `paper-run` 生成 TAKER 时使用 Gamma 市场快照价格，而不是对应方向订单簿的实时 ask；持仓退出也依据历史价格而非实时 bid，模拟成交偏乐观或不一致。

### 已调整

- VPS 专用配置关闭 HTTP cache、关闭 stale fallback、关闭 live market pool 回退；实时市场发现失败时不生成新的开仓候选。
- `paper-run` 产生 BUY 候选后，读取对应 YES/NO token 的 CLOB 实时订单簿：以 ask 作为模拟入场基础，以 bid 作为开放持仓的止盈/止损判断基础。
- 若实时盘口缺失、bid/ask spread 超过阈值，或按 ask 重估后净 edge 不足，则跳过模拟开仓。
- BTC spot 上下文若超过 `15` 分钟没有新 K 线，方向性新开仓会被拦截。
- 将调度拆成两条链：`live_paper_cycle.sh` 每 `5` 分钟执行实时模拟；`research_cycle.sh` 每小时执行深度回测和参数研究。

### 验证

- VPS 严格实时配置显示 `cache.enabled=false`、`stale_if_error=false`、`fresh_market_ttl_seconds=0`，缓存目录文件数为 `0`。
- 快速实时链手工验证耗时 `16` 秒：BTC live `1` 秒、paper-run `5` 秒、spread scan `4` 秒、flow scan `6` 秒；错误日志为空。
- 已有模拟持仓由实时 bid 估值：May 25 `above 78k` 的 `BUY_NO` bid 约 `0.998`、浮盈约 `8.8%`；May 26 `above 76k` 的 `BUY_YES` bid 约 `0.93`、浮盈约 `4.8%`。

### 边界

实时 ask/bid 模拟明显比快照价更可信，但仍不等同于真实下单。未来进入极小额实盘前，还需要验证订单发出延迟、部分成交、撤单、余额与签名错误、盘口成交深度以及异常断连时的保护动作。

## 2026-05-25：加入真实下单风险的影子压力层

### 目标

策略候选即便在实时 ask 下看起来有 edge，真实订单仍可能因提交延迟、部分成交、撤单失败或鉴权/余额异常而恶化。该阶段先把这些风险量化，不接钱包、不发送订单，也不直接改写已有 paper PnL 基线。

### 已实现

- 每轮 `paper-run` 对 `TAKER` 候选额外输出 `execution_stress_<timestamp>.csv`。
- 用 ask 向不利方向移动 `0.0025` 与 `0.01` 模拟延迟/盘口变差；净 edge 低于 `0.003` 时标记应拒单。
- 用 `50%` 与 `25%` 成交比例模拟部分成交；剩余委托超过允许比例时标记应撤销残单。
- 记录签名/鉴权失败、余额/allowance 不足和部分成交后撤单失败的 fail-safe 动作：暂停新单、连续失败熔断，或冻结该市场直到完成对账。
- 风控门槛集中在 `[execution_stress]` 配置，便于累积样本后调整，而不是凭感觉修改主策略。

### 判断

这解决的是“理论交易在执行层是否还站得住”的验证缺口，并不证明策略已适合实盘。下一步先在 VPS 实时链上积累压力报告，再加入持久化的 pending/partial/cancel-pending 订单状态模拟；在执行压力通过率与前瞻 PnL 都稳定前，仍不建议实盘。

## 2026-05-26：影子订单事件与执行风险累计统计

### 修正与新增

- 修正 `robust` 统计口径：部分成交后撤销残单属于风险处理动作，不等同于价格 edge 已失效；`robust` 只由基准成交与延迟价格恶化场景决定。
- 每轮新增 `shadow_order_events_<timestamp>.csv`，把候选展开为 `SUBMITTED`、`FILLED`、`PARTIALLY_FILLED`、`CANCELED_REMAINDER`、`CANCEL_PENDING` 或 `REJECTED` 事件。
- 当模拟出现部分成交后撤单未确认，影子事件仍以完整名义金额作为 `reserved_exposure`，避免未来实现中在状态未知时再次加仓。
- 新增累计 `execution_stress_report.csv`，分开记录实时观察轮数、理论候选数、延迟压力通过/拦截、按 `FAK` 路径发生的部分成交撤余单和 fail-safe 场景数。

### 当前边界

这一层已经能审计“如果订单生命周期变复杂，应采取什么动作”，但仍属于影子文件事件，而不是会跨轮拦截主 paper 仓位的持久化订单账本。下一步应让 `CANCEL_PENDING` 等未确认状态跨轮保留并阻止冲突新单，然后才能更接近极小额实盘演练。

## 2026-05-26：夜间 VPS 复盘后升级开仓安全闸

### 夜间结果

- 北京时间 `2026-05-25 22:00` 至 `2026-05-26 08:50`，实时 paper 链运行 `124` 轮，扫描累计 `5755` 个市场。
- 仅出现 `3` 个 `TAKER`，全部集中于 `BUY_NO above 78k`，分别对应 May 25、May 26 和 May 27 市场；候选集中度仍偏高。
- 最新深度回测为 `18` 笔、胜率 `55.6%`、PnL `-17.49 USDC`、费用 `6.68`、滑点 `0.56`、MTM 最大回撤 `2.4%`，`readiness=not_ready`。
- strike 维度中，`76000` 贡献 `-11.33`、`78000` 贡献 `-8.55`，主要亏损仍来自接近现货附近、容易来回波动的日结 strike。
- 实时日志仅出现一次无效订单簿 `404` 跳过；深度研究错误日志为空，未见 `IncompleteRead` 持续恶化。

### 发现的安全缺口

- 新压力层覆盖的两笔 `BUY_NO above 78k` 候选，其 expected net edge 仅约 `0.0018` 与 `0.0027`。
- 它们在 `baseline` 场景就低于最低存活净 edge `0.003`，更无法覆盖延迟引起的价格恶化；但旧流程仍先建立 paper 持仓、再写压力报告。

### 已调整

- 新开仓流程现在先记录拟 `TAKER` 候选并运行执行压力测试，再决定是否创建 paper 持仓。
- 未通过基准或延迟价格压力的候选仍保留在 `execution_stress` 报告中，但主 `paper_run` 会转为 `SKIP/HOLD`，不再让薄 edge 形成新模拟持仓。
- 部分成交、撤单失败、余额/签名失败仍继续作为影子订单生命周期观察，等待跨轮状态持久化后再升级为更完整的硬风控。

### 判断

昨夜不是盈利验证成功的一夜，而是暴露并修掉一个实盘前必须处理的执行缺口。当前 PnL 为负、交易数少且候选过度集中在 `above 78k BUY_NO`，仍不建议实盘。

## 2026-05-26：修复实时市场发现被历史市场数量误判

### 今日阶段结果

- 截至北京时间 `2026-05-26 19:13`，今日实时 paper 运行 `235` 轮、累计观察 `7560` 个市场行；安全闸启用前仅有 `2` 笔 `BUY_NO above 78k` 拟成交，此后没有新增 `TAKER`。
- 最新深度回测扩大到 `104` 个市场、`26` 笔交易，胜率 `61.5%`，PnL `+3.23 USDC`，费用 `8.99`，滑点 `0.81`，MTM 最大回撤 `3.3%`。
- `78000` strike 当前贡献 `+6.61`，但 `76000` 仍拖累 `-6.54`；正结果仍不足以证明稳定盈利。

### 发现的问题

- 下午的实时链连续出现 `paper_run markets=0`，同时日志显示 live API 实际已经返回 `48` 至 `56` 个当前市场。
- 原因是实时链将本轮 live 市场数与 SQLite 累计的历史研究市场数比较。本地累计市场增长到 `104` 至 `115` 个后，合法的 live 活跃市场也会被错误视为覆盖不足。
- 该错误不会造成过期数据下单，但会过度保守地停止所有实时候选验证，使正负策略都无法继续积累前瞻样本。

### 已调整

- 深度研究链仍保留“live 覆盖不足时允许用本地数据回放”的质量保护。
- 实时 paper / spread 链改为只依据当轮 live 活跃市场是否达到最低覆盖数量判断健康，不再与历史累计 universe 比较。
- 实时链仍不允许使用 SQLite 旧市场或 HTTP stale cache 替代新开仓数据；这次修复是恢复有效 live 数据，不是放宽过期数据使用边界。

### 判断

今天回测 PnL 首次恢复为小幅正值，但样本仍少，且实时验证曾被错误中断。修复后需要继续观察有效 live 样本能否持续产生并在执行压力安全闸下维持正结果，当前仍不建议实盘。
