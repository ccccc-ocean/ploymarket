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
```

复盘时重点看：

- 买入是否发生在价格已经过高的时候。
- `fee` 和 `slippage` 是否明显吞掉收益。
- 止损是否太紧或太松。
- 止盈是否过早。
- 盈亏是否来自少数偶然交易。
- 是否有大量 `REJECTED`，说明风控参数可能过紧。

## 查看风控配置说明

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml explain-risk
```

## 常见问题

### API 偶尔报 IncompleteRead 或 RemoteDisconnected

这是公共接口或网络连接不稳定导致的。当前代码已经做了重试和单市场跳过。后续会加入本地缓存，降低重复请求。

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
