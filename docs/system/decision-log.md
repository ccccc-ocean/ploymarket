# 决策日志

tags: #decision-log #system #polymarket

这个文件记录重要项目决策。它不是流水账，而是回答“我们为什么这样做”。

## 2026-05-07：先做只读模拟盘，不碰实盘

决策：

- 第一阶段只接公开只读数据。
- 不使用私钥。
- 不下真实订单。

原因：

- 当前策略还没有验证 edge。
- 风控参数还在学习阶段。
- Polymarket 的订单、撮合、结算机制需要先理解。

结果：

- 项目先实现 `discover`、`signals`、`backtest` 和 `explain-risk`。

## 2026-05-08：信号必须看 net edge

决策：

- `BUY_YES` 不能只看 gross edge。
- 必须扣除 Taker fee、滑点和安全边际后的 net edge。

原因：

- Polymarket Taker fee 使用 `p * (1 - p)` 曲线。
- 小 edge 很容易被交易成本吃掉。
- 实盘盈利目标要求我们尽早把交易摩擦纳入系统。

结果：

- 新增 `costs.py`。
- 回测 CSV 新增 `fee`、`slippage`、`net_edge`。

## 2026-05-10：把 `docs/` 作为 Obsidian vault

决策：

- 继续保留 `docs/` 作为 GitHub 文档目录。
- 同时让它成为 Obsidian 可打开的知识库。
- 使用 Markdown 双链组织学习内容。

原因：

- 代码和学习笔记需要长期同步。
- Obsidian 适合管理概念、复盘和学习路径。
- GitHub 适合版本管理和回溯。

结果：

- 新增 `00-home.md`。
- 新增学习地图、决策日志、市场分类笔记和模板。

## 下一条待决策

下一步代码优先级：

- 选项 A：市场分类。
- 选项 B：本地行情缓存。
- 当前建议：先做市场分类，再做缓存。
