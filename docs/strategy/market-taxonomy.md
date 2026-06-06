# 预测市场分类笔记

tags: #strategy #market-taxonomy #btc #polymarket

## 为什么要分类

我们现在抓到的市场只要包含 `BTC` 或 `Bitcoin` 就会进入候选池。但“BTC 相关”不是一个策略类别。

比如下面三种市场完全不同：

- `Will Bitcoin reach $85,000 in May?`
- `MicroStrategy sells any Bitcoin by December 31, 2026?`
- `Will Anthropic flip BTC by December 31?`

它们都和 BTC 有关，但 edge 来源、信息来源、结算方式和风险完全不同。

如果把它们混在一起回测，策略可能出现假象：

- 价格市场亏钱，事件市场赚钱，被平均值掩盖。
- 某个偶然事件贡献全部收益，看起来像策略有效。
- 风控参数对一种市场有效，对另一种市场无效。

## 当前分类

### `touch_above`

典型问题：

- `Will Bitcoin reach $100,000 in May?`

特点：

- 路径依赖，只要期间触碰上方目标就可能结算 YES。
- 时间价值和波动率很重要，不能简单等同于到期 above。
- 当前只允许保守 `BUY_NO` 候选，`BUY_YES` 先观察。

### `touch_below`

典型问题：

- `Will Bitcoin dip to $70,000 in May?`
- `Will Bitcoin drop below $72,000 this week?`

特点：

- 路径触碰下方目标，容易受突发瀑布和消息面反转影响。
- 当前样本中薄 edge 容易被反弹、费用和滑点吞掉。
- 默认观察，不主动开仓。

### `expiry_target`

典型问题：

- 目标价问题但无法明确判断是触碰还是到期口径。

特点：

- 结算语义不清时，交易前必须更保守。
- 默认观察，直到分类器或市场元数据能确认口径。

### `above_below_expiry`

典型问题：

- `Will the price of Bitcoin be above $80,000 on May 8?`

特点：

- 到期时点 above/below 某个 strike。
- 核心风险来自 BTC 接近 strike 时的假突破和订单簿跳变。
- 当前重点研究 `BUY_NO`，并使用 strike 安全带、BTC regime 和连续亏损暂停过滤。

### `up_down_short_term`

典型问题：

- `Bitcoin Up or Down on May 6?`

特点：

- 时间很短。
- 更像短周期方向盘，依赖快速、干净的现货数据和订单簿。
- 允许双边，但需要更短窗口和更高 edge。

### `range_bucket`

典型问题：

- `Will Bitcoin close between $80,000 and $82,000 on May 8?`

特点：

- 不是单一 above/below，而是落入区间。
- 两侧边界都重要，需要避免在接近边界时追单。
- 当前观察，不自动交易；后续需要双边界模型后再重新开启。

### `company_treasury`

典型问题：

- `MicroStrategy sells any Bitcoin by December 31, 2026?`
- `Will MicroStrategy announce holding 1M+ BTC by December 31, 2026?`

特点：

- 不是直接交易 BTC 价格。
- Edge 来自公司公告、财报、链上持仓、新闻和管理层行为。
- 价格历史动量不一定有意义。
- 需要事件研究，不适合直接套 BTC 价格策略。

### `indirect_event`

典型问题：

- `Will Anthropic flip BTC by December 31?`

特点：

- 间接关联 BTC。
- 可能只是搜索关键词命中。
- 大概率不适合 BTC 自动交易系统。

### `unknown`

无法可靠分类的市场。

默认处理：

- 可以显示。
- 不进入自动回测。
- 不进入未来实盘候选。

## 当前项目应该怎么用

下一步代码可以做一个轻量分类器：

```text
Market question + slug
  -> classify_market()
  -> market_type
  -> CLI 输出
  -> 回测过滤
```

第一版不需要机器学习，用关键词规则即可。

建议规则：

- 包含 `reach`, `hit` + Bitcoin/BTC + 上方目标 -> `touch_above`
- 包含 `dip`, `drop` + Bitcoin/BTC + 下方目标 -> `touch_below`
- 包含 `above`, `below` + 具体到期日期 -> `above_below_expiry`
- 包含 `up or down` -> `up_down_short_term`
- 包含 `between` 或价格区间 -> `range_bucket`
- 包含 `MicroStrategy`, `MSTR`, `Strategy` -> `company_treasury`
- 否则如果只是含 BTC -> `indirect_event`
- 无法判断 -> `unknown`

状态：第一版已经实现。

代码位置：

- [classifier.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/classifier.py)

可运行示例：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml discover --market-type above_below_expiry
```

`discover`、`signals`、`backtest` 都支持 `--market-type`。

## 对策略的影响

第一阶段优先对 `above_below_expiry` 和 `up_down_short_term` 做策略研究；`touch_above` 只允许保守 NO 侧，`range_bucket` / `touch_below` / `expiry_target` 暂时观察。

原因：

- 它最接近 BTC 交易者的已有认知。
- 可以接外部 BTC 价格源增强模型。
- `above_below_expiry` 的核心不是硬编码某个固定 strike，而是动态判断当前 BTC 现货与 strike 的距离、`above/under` 方向、资金流和盘口成本。
- `range_bucket` 需要同时考虑上下边界，不能只看一个目标价。
- `touch_*` 市场路径依赖更强，不能直接平移到期市场策略。

执行条件集中记录在 [BTC 策略执行条件](/Users/pizza_yang/code/ploymarket/docs/strategy/btc-execution-conditions.md)。

`company_treasury` 可以作为独立研究方向，但不能和价格策略混跑。

`indirect_event` 先排除。
