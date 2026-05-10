# 2026-05-10 学习与构建计划

tags: #daily-note #learning #plan #polymarket

## 今天的目标

把 Obsidian 纳入项目工作流，让它成为持续学习 Polymarket 和记录模拟盘实验的主入口。

同时继续沿着上一轮学习推进：

- 从 Polymarket 底层机制出发。
- 强化对费用、撮合、结算和失败状态的理解。
- 把知识转成项目里的下一步功能。

## 今天先完成

- [x] 创建 Obsidian 主页：[[../00-home|Ploymarket Knowledge Vault]]
- [x] 创建学习地图：[[learning-map|学习地图]]
- [x] 创建决策日志：[[../system/decision-log|决策日志]]
- [x] 创建市场分类笔记：[[../strategy/market-taxonomy|预测市场分类笔记]]
- [x] 创建 Obsidian 模板。
- [x] 实现第一版市场分类器。
- [x] CLI 支持 `--market-type` 过滤。

## 今天建议继续学

### 主题 1：为什么不能混合评估所有 BTC 市场

BTC 相关市场至少有三类：

- 纯 BTC 价格市场。
- BTC 间接事件市场。
- 公司或人物相关 BTC 市场。

它们的 edge 来源完全不同。把它们混在一起回测，会让策略表现失真。

### 主题 2：为什么下一步应该做市场分类

我们现在的 `discover` 会抓很多 BTC 相关市场。比如：

- `Will Bitcoin reach $85,000 in May?`
- `MicroStrategy sells any Bitcoin by December 31, 2026?`
- `Will Anthropic flip BTC by December 31?`

这些都含 BTC，但不能用同一个信号解释。

### 主题 3：为什么本地缓存也很重要

公共 API 偶尔会慢或截断。没有缓存时，学习和回测都容易被网络噪音打断。

不过从策略质量角度看，市场分类更优先，因为它决定“我们到底在交易什么”。

## 推荐下一步代码任务

优先任务：市场分类。

预期效果：

- 每个市场打上 `price_target`、`price_range_daily`、`company_treasury`、`indirect_event`、`unknown` 等标签。
- CLI 输出分类。
- 回测可以只跑某一类市场。
- 文档和复盘能按市场类型分析。

状态：第一版已完成，后续需要用真实市场样本校准规则。

## 今天结束前要更新

- [[progress-log|学习进度记录]]
- [[../system/current-state|当前系统状态]]
- [[../system/roadmap|项目路线图]]
- 如果跑了模拟盘，新增一份 `docs/records/YYYY-MM-DD-paper-session.md`。
