# 2026-06-15 100 USDC 实盘候选

## 结论

当前全策略历史回放为负，不能直接实盘。亏损主要来自：

- `above_below_expiry / NO`
- `up_down_short_term`
- `touch_below`
- `touch_above` 样本少且近期波动大

截至 2026-06-15，唯一具有近期 forward paper 正向证据、且样本相对集中的主策略方向是
`above_below_expiry / YES`。候选配置因此只允许该方向入场。

## 候选规则

- 配置：`config/vps.live_candidate_100.toml`
- 初始资金：100 USDC
- 单笔名义金额：2 USDC
- 最多同时持仓：2
- 总敞口上限：4.2 USDC
- 单日已实现亏损上限：3 USDC
- 账户最大回撤：6%
- 单笔止损：15%
- 8% 部分止盈，20% 全量止盈
- 实时 ask 重定价后最低净 edge：1%
- 最大 spread：4%
- YES 入场价格：0.15 至 0.80
- 禁用所有 probe / challenge 仓
- 禁止所有 NO、短周期涨跌、touch 和 target 类入场

## 上线边界

代码当前只有实时行情驱动的模拟成交与 shadow execution stress，没有私钥签名、余额授权或真实订单提交链路。
因此该配置是“实盘候选的独立 forward paper 账户”，不是实际资金账户。

启用真实订单前至少需要：

1. 独立候选账户连续运行并产生足够样本。
2. 确认净 PnL、最大回撤、滑点压力测试均达标。
3. 单独实现并审计签名、授权、下单、撤单、部分成交和故障熔断。
4. 由账户所有者明确授权后再启用真实订单。
