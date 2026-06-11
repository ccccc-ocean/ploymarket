# 2026-06-11 策略 review & 改进进度档

> 用于跨会话续接。任何下次打开新会话的 Claude / 我自己，先读这份文档再继续。

---

## 0. 背景一句话

VPS 回测开仓数越来越少、PnL 退化。本次会话做了一次端到端 review（代码 + `data/*.csv` 历史），定位了 5+ 个叠加在一起的过滤层，并开始动手修最 critical 的两项。目标仍是“稳定 PnL → 尽快上 live”。

---

## 1. 诊断结论（已交付）

详见会话记录。要点：

- **Critical**
  1. `src/ploymarket_sim/signals.py:42-50` — `allow_buy_yes` 只放 `up_down_short_term`，下面给 `above_below_expiry` / target-like 写好的 `×2/×3` 阈值全是死代码。这是 `live_universe_report.csv` 里 30 个 above_below_expiry 市场几乎不开仓的最简单解释。
  2. `src/ploymarket_sim/cli.py:609-620` `_fresh_paper_btc_candles` — 15 分钟硬上限是全局熔断，本地 `btc_price_candles.csv` 已经 stale 5.5 天，直接抹掉所有 BTC 相关 directional 信号。
  3. **fee = 71% gross PnL**（`data/strategy_sweep.csv` 110 trade / fee $47.79 / gross $66.63）— `trade_size_usdc=3.0` + 2% taker 在经济上不成立。
  4. **`strategy_sweep` 已失去信号**：10 组参数 100% 相同 PnL，说明下游 gate 主导而非 signal 阈值，继续调 signal 是浪费时间。
- **High**：`live_reprice_edge_multiplier=2.0` 过严；range/touch 硬价格上限（0.88 / 0.75）砍掉真 edge（`blocked_edge_report.csv` 有 5–12% edge 被毙）；15+ probe family 阈值高于实际可达 edge；`_positive_edge_blocked_market_types` 字符串对不上的死 gate；BUY_NO 阈值缺对称放大。
- **Medium**：`cli.py` 2640 行单文件无法独立测；paper_account_pnl ($15.99) vs replay_pnl ($59.67) 持续背离；没有 forward-only holdout。

完整数据证据：见 `data/daily_report.csv` 最新行、`data/paper_report.csv` 13 个窗口 taker 序列 `0,0,0,0,0,0,0,0,13,51,7,6,0`、`data/blocked_edge_report.csv` 多个 ≥5% edge 被拒。

---

## 2. 本次会话动手做的（按完成状态）

### ✅ Done（2026-06-11 会话）
- **Critical #1**：`signals.py` 把 `allow_buy_yes` 扩到 `{up_down_short_term, above_below_expiry}` ∪ target-like。已有的 `above_below_expiry × 2/3`、`target_like × 3` 阈值倍率现在真正生效。
  - **未做 BUY_NO 对称放大**：尝试后被 `test_backtest::test_btc_weakness_filter_does_not_block_buy_no` 挡回，说明对称放大会把真实下行信号挤死，且本次目标是恢复开仓，不是收紧。改入 [📌 待续] 留待数据驱动决策。
  - 新增单测 `test_above_below_expiry_allows_buy_yes_after_unblock`、`test_above_below_expiry_buy_yes_respects_multiplied_threshold`。
- **Critical #2**：`RiskConfig` 新增 `btc_candle_max_age_seconds: int = 3600`；`config/default.toml [risk]` 同步；`cli.py:_fresh_paper_btc_candles` 改读这个字段（向后兼容：未配置时退回 `max(15min, fidelity_floor)`）。
  - 新增单测 `test_btc_candle_max_age_is_configurable`；老 `test_stale_btc_candles_are_not_accepted_for_paper_entries` 更新到 3600s 边界。
- **顺带修复 4 个旧 test_backtest 测试**：原来假定 signals 层完全禁掉 BUY_YES，trades 应为空。Critical #1 后 signals 会发 BUY_YES 信号，由 market_rules 层（distance/price cap）拦截并写入 REJECTED 行。断言更新为「无 BUY_YES action + 有对应 REJECTED reason」。
  - `test_far_price_target_reach_is_rejected_by_spot_distance` — 改断 REJECTED+"距离过远"
  - `test_near_price_target_dip_buy_yes_is_observe_only` — 改用弱 momentum 让 ×3 阈值过滤
  - `test_price_target_buy_yes_no_longer_opens_stop_loss_path` → 重命名为 `test_price_target_buy_yes_stop_loss_path_uses_target_cooldown`，断 BUY_YES + SELL_YES(止损) 全链路
  - `test_price_target_buy_yes_rejects_poor_reward_price` — 改断 REJECTED+"价格过高"
- **全套 201/201 测试通过**（`/usr/local/bin/python3 -m pytest tests/`）。

### 📌 待续（下一次会话从这里继续）
按优先级：
1. **VPS 跑 paper-trading 7 天验收 Critical #1 + #2 效果**：daily_report 里 `latest_taker` 是否回到 ≥10/日、win_rate 是否仍 ≥55%。同步看 above_below_expiry 是否真的开始出 BUY_YES（这是本次 fix 的核心信号）。
2. **决策点：BUY_NO 是否需要 ×2/×3 对称放大**：本次回退是因为 `test_btc_weakness_filter_does_not_block_buy_no` 报错。但 review 数据里 BUY_NO 早就占主导，所以放大可能仍是对的方向。等 #1 跑出实盘数据再判断（如果 BUY_YES 现在开起来了、BUY_NO 仍主导且胜率低 → 加放大；如果 BUY_NO 胜率正常 → 不动）。
3. **High #5**：`live_reprice_edge_multiplier` 从 2.0 调到 1.3，盯一周。
4. **High #6**：把 `range_buy_yes_max_price` / `range_buy_no_max_price` 改成 price-edge 联合曲线（替代硬阈值）。
5. **High #7**：合并 15+ probe family → 3–4 个，阈值降到 `paper_probe_min_edge * 2`，按 hit_rate 自动停低胜率 family。
6. **Medium**：拆 `cli.py` 的 filter chain 成独立模块；daily_report 增加 per-gate skip 计数（这一步做完，下次再退化就能秒级定位哪层在收紧）。
7. **Medium**：固定最后 14 天 BTC candle 为 forward holdout，所有调参不许用它；连续 ≥3 天 forward 不退化才允许进 live。
8. **经济性**：`trade_size_usdc` 临时调 10，或区分 maker / taker（maker 主入口、taker 仅高 edge 时）。
9. **基础设施**：修 BTC candle fetcher（5.5 d gap 是 cron / 拉数链路问题，独立工单）。
10. **基础设施**：`live_pipeline_healthy=False / readiness=not_ready`（daily_report 最新行）单独排查。

---

## 3. 关键文件索引

| 路径 | 用途 | 本次会话改动 |
|---|---|---|
| `src/ploymarket_sim/signals.py` | 信号生成 | Critical #1 |
| `src/ploymarket_sim/strategy_profiles.py` | 按 market type 切配置 | 未改 |
| `src/ploymarket_sim/market_rules.py` | range/target/strike gates | 未改 |
| `src/ploymarket_sim/risk.py` | 风控（exposure / drawdown / stop） | 未改 |
| `src/ploymarket_sim/costs.py` | fee + slippage + safety margin | 未改 |
| `src/ploymarket_sim/config.py` | dataclass 配置 schema | Critical #2 |
| `src/ploymarket_sim/cli.py` | 单文件 2640 行，含 `_run_paper_scan` / `_fresh_paper_btc_candles` / `_live_paper_entry_plan` / 15+ probe family | Critical #2 |
| `config/default.toml` | 运行时配置 | Critical #2（新增字段） |
| `tests/test_signals.py` | signals 单测 | Critical #1 新增 case |
| `tests/test_paper.py` 或新增 `tests/test_cli_freshness.py` | freshness gate 单测 | Critical #2 新增 case |

---

## 4. 下次会话开机三件事

1. 读这份文档 + `data/daily_report.csv` 最新一行（看 `latest_taker / latest_skip / paper_account_pnl / live_pipeline_healthy`）。
2. 跑 `pytest tests/test_signals.py tests/test_paper.py -v`（或全量 `pytest`）。
3. 检查 `data/btc_price_candles.csv` 末行时间是否还 stale（>1h 就先修拉数 cron 再谈别的）。

---

## 5. 待定 / 需要用户拍板的设计决策

- `trade_size_usdc` 何时从 3 抬到 10/20？（要权衡 paper 损耗）
- 是否引入 maker 入口（需要新增 order placement 路径，工作量较大）
- forward holdout 用最后 14 天还是 7 天？
- live 切换的金额起点（5 / 10 / 20 USDC 都可）
