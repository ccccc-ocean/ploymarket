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

## 初步分类

### `price_target`

典型问题：

- `Will Bitcoin reach $100,000 in May?`
- `Will Bitcoin dip to $70,000 in May?`

特点：

- 和 BTC 价格路径直接相关。
- 需要 BTC 现货/永续价格源。
- 到期时间和波动率很重要。
- 适合先做概率模型和回测。

### `price_range_daily`

典型问题：

- `Will the price of Bitcoin be above $80,000 on May 8?`
- `Bitcoin Up or Down on May 6?`

特点：

- 时间很短。
- 临近结算时价格会快速接近 0 或 1。
- 对数据延迟和结算规则非常敏感。
- 当前阶段可以观察，但不优先做实盘。

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

- 包含 `reach`, `dip`, `hit` + Bitcoin/BTC -> `price_target`
- 包含 `above`, `below`, `up or down` + 具体日期 -> `price_range_daily`
- 包含 `MicroStrategy`, `MSTR`, `Strategy` -> `company_treasury`
- 否则如果只是含 BTC -> `indirect_event`
- 无法判断 -> `unknown`

状态：第一版已经实现。

代码位置：

- [classifier.py](/Users/pizza_yang/code/ploymarket/src/ploymarket_sim/classifier.py)

可运行示例：

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml discover --market-type price_target
```

`discover`、`signals`、`backtest` 都支持 `--market-type`。

## 对策略的影响

第一阶段优先对 `price_target` 和 `price_range_daily` 做策略研究，但两者不能共用完全相同的执行条件。

原因：

- 它最接近 BTC 交易者的已有认知。
- 可以接外部 BTC 价格源增强模型。
- `price_target` 相比日内结算市场，时间压力略低。
- `price_range_daily` 的核心不是硬编码某个固定 strike，而是动态判断当前 BTC 现货与 strike 的距离、`above/under` 方向、资金流和盘口成本。

执行条件集中记录在 [BTC 策略执行条件](/Users/pizza_yang/code/ploymarket/docs/strategy/btc-execution-conditions.md)。

`company_treasury` 可以作为独立研究方向，但不能和价格策略混跑。

`indirect_event` 先排除。
