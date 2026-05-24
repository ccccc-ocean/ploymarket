# BTC 策略执行条件

tags: #strategy #btc #execution #paper-trading

这份笔记记录当前 BTC Polymarket 策略应该如何判断“能不能交易”。它不是盈利承诺，也不是实盘开关；它的作用是把我们已经确认有用的条件集中起来，避免下次继续时又回到“看到某个 strike 赚钱就硬编码”的旧路。

## 核心原则

策略不能硬编码某个固定 strike，例如 `$74k`、`$76k`、`$78k`。

原因很简单：BTC 行情会移动。今天 `$76k` 可能是高确定性事件，明天 BTC 如果快速跌到 `$72k`，同一个 `$76k above` 就可能变成高风险突破盘。真正应该判断的是：

- 当前 BTC 现货价格在哪里。
- market strike 距离现货有多远。
- 市场是 `above` 还是 `under/below`。
- 当前 Polymarket 价格是否已经反映了大部分确定性。
- 最近资金流是在支持 YES，还是支持 NO。
- 扣除手续费、滑点、价差和尾部风险后，是否还有净 edge。

## 当前市场类型范围

优先研究：

- `price_range_daily`: 例如 `Will Bitcoin be above $78,000 on May 22?`
- `price_target`: 例如 `Will Bitcoin hit $100,000 in May?`

暂不自动交易：

- `company_treasury`
- `indirect_event`
- `unknown`

这些市场可以观察，但不能和 BTC 价格策略混在同一个 PnL 里判断。

## 统一看待 above 与 under

`above $78k` 一直没突破会亏，不代表所有高 strike 都不能做。它可能在 BTC 接近突破、盘口没有充分定价、并且资金流支持 YES 时变成机会。

同理，`under $60k` 不能因为 YES 便宜就买。如果 BTC 现货远高于 `$60k`，这个 YES 只是低价彩票，不是稳定套利。

所以 `above` 和 `under/below` 的第一层判断应该一致：

- `above` 市场：strike 高于现货越远，买 YES 越需要额外确认。
- `below/under` 市场：strike 低于现货越远，买 YES 越需要额外确认。
- 接近现货的 strike 才是短周期 BTC 市场更值得研究的位置。
- 已经很确定的市场也不能盲目买，因为 YES 价格太接近 1 时，剩余收益可能覆盖不了费用和尾部风险。

## 当前可用信号

### 1. Strike 距离

代码会解析问题里的美元 strike，并计算：

```text
strike_distance_pct = (strike - current_btc_price) / current_btc_price
```

当前风险标签：

- `far_above_spot`: above strike 明显高于现货。
- `far_below_spot`: below/under strike 明显低于现货。
- `near_spot`: strike 接近现货。
- `in_the_money_or_unclear`: 可能已经在价内，或问题表达不够明确。
- `no_strike`: 没有解析出美元 strike。

这只是诊断标签，不是单独交易信号。

### 2. Polymarket 资金流

`flow-scan` 会按 `conditionId` 拉取最近交易流，并统计：

- `buy_yes_usdc`
- `sell_yes_usdc`
- `buy_no_usdc`
- `sell_no_usdc`
- `net_yes_usdc`
- `net_no_usdc`
- `large_trade_count`
- `unique_wallets`
- `top_wallet`
- `flow_signal`

当前 `flow_signal`：

- `YES_PRESSURE`: 最近净资金明显偏向 YES。
- `NO_PRESSURE`: 最近净资金明显偏向 NO。
- `MIXED`: 多空不够一致。
- `NO_RECENT_TRADES`: 最近无交易。

注意：大额钱包不等于聪明钱。它可能是对冲、套利、做市库存调整或错误交易。资金流只能辅助确认，不能单独触发交易。

### 3. Polymarket 价格与成本

任何交易都必须看净 edge，而不是只看方向。

必须扣除：

- taker fee 或 maker 成交成本。
- 买卖价差。
- 预估滑点。
- 安全边际。
- 退出时可能卖不掉的流动性风险。

如果 YES 已经接近 `1`，即使方向大概率正确，也可能因为收益太薄而不值得买。

### 4. BTC 短线动量

当前已有坏条件过滤器：

- `YES >= 0.50`
- BTC 过去 1 小时收益 `<= -0.25%`

命中时，不允许做多 YES。这个规则不是为了预测上涨，而是先排除历史上明显差的环境。

## 当前推荐执行条件草案

这是研究草案，不是默认实盘规则。后续必须通过回测验证后才能进入模拟盘执行层。

### 可以考虑 BUY_YES 的条件

- 市场属于 `price_range_daily` 或 `price_target`。
- 当前 market strike 与 BTC 现货关系可解释，不是盲目固定 strike。
- 对 `price_target` / `price_target_daily`，必须能拿到 BTC 现货确认；缺少 BTC 现货时不允许入场。
- 对 `price_target` / `price_target_daily`，目标 strike 与 BTC 现货距离默认不能超过 `2.5%`；更远的 `reach/hit/dip/drop` 目标只观察，不吃单。
- 对 `above` 市场，不能在 `far_above_spot + NO_PRESSURE` 时买 YES。
- 对 `under/below` 市场，不能在 `far_below_spot + NO_PRESSURE` 时买 YES。
- `near_spot + YES_PRESSURE` 可以进入候选，但仍要通过净 edge、价差和风控。
- 如果市场已经明显价内，只能在剩余收益覆盖成本和尾部风险时考虑。
- 每笔交易必须能写出可复盘原因，不能只有“价格看起来便宜”。

### 必须跳过的条件

- `company_treasury`、`indirect_event`、`unknown` 市场。
- 没有足够价格历史或 BTC 现货上下文。
- `YES` 或 `NO` 价格过于极端，净收益无法覆盖成本。
- 盘口 spread 超过风控阈值。
- 最近资金流与入场方向明显相反。
- 单日亏损、最大回撤、总敞口、单市场敞口触发风控。
- 同一市场已有模拟持仓时，不重复开仓。
- 同一市场刚触发止损后，必须等待较长冷却期结束。
- `price_target` 止损后的同方向冷却更长，当前默认 `21600` 秒，避免在同一个 weekly target 上连续补刀式亏损。
- 同一市场触发止盈后只进入短冷却；止盈是兑现利润，冷却结束后仍允许重新评估开仓。
- 止盈后重新入场必须满足更高 edge 门槛，避免“卖出落袋后马上追进”导致手续费和滑点变多。
- 浮盈达到分批止盈阈值时，先卖出部分仓位，剩余仓位继续用移动止盈保护。
- `above` 市场买 `NO` 时，如果 BTC 已接近或站上 strike，暂停逆突破方向；`below/under` 市场买 `NO` 时规则反向处理。
- 交易理由依赖未来信息，或依赖手工挑出来的固定 strike。

## 回测验证方向

下一步应该验证以下组合是否改善 PnL：

- `near_spot + YES_PRESSURE`
- `near_spot + MIXED`
- `far_above_spot + NO_PRESSURE`
- `far_below_spot + NO_PRESSURE`
- `in_the_money_or_unclear + YES_PRICE_HIGH`

重点不是找到一个看起来漂亮的单轮结果，而是确认：

- 交易次数足够。
- 多个日期、多种行情阶段都有效。
- 扣除费用和滑点后仍为正。
- 最大回撤可接受。
- 亏损交易可以解释，并能归类到可改进的条件。

## 实盘前结论

当前仍不建议实盘。

我们已经从“固定 strike 经验判断”升级到“动态现货距离 + 资金流 + 成本 + 风控”的框架，但这个框架还需要和历史 PnL 绑定验证。只有当执行条件在足够样本里稳定改善 PnL，并且模拟盘连续运行表现健康，才进入小资金实盘准备。
