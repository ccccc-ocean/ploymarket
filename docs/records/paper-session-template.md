# 模拟盘记录模板

日期：

## 运行命令

```bash
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml discover
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml signals
env PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ploymarket_pycache python3 -m ploymarket_sim.cli --config config/default.toml backtest
```

## 市场概况

- 发现 BTC 市场数量：
- 主要市场类型：
- 流动性最好的市场：

## 信号概况

- `BUY_YES` 数量：
- `HOLD` 数量：
- `AVOID` 数量：
- 最值得复盘的信号：

## 回测结果

- 总交易次数：
- 盈利市场：
- 亏损市场：
- 最大单笔亏损：
- 最大单笔盈利：

## 风控观察

- 是否触发止损：
- 是否触发止盈：
- 是否有交易被风控拒绝：
- 仓位是否感觉过大：

## 结论

本次是否发现可继续研究的现象：

下次要改的参数或代码：
