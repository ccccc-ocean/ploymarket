# VPS 模拟盘运行手册

## 目标

VPS 目前只用于实时公开行情抓取、信号、回测和 paper-run，不配置钱包、私钥或实盘下单能力。它的价值是连续积累网络更稳定的前瞻样本，而不是提前放宽实盘门槛。

## 数据隔离

仓库中的 `data/` 包含既有研究结果，不能把它与 VPS 新产生的样本直接混合作为上线依据。服务器运行时使用未提交的 `config/vps.local.toml`：

- HTTP 缓存：VPS 实时候选链禁用，不使用 stale HTTP 响应
- SQLite 存储：`runtime/data/ploymarket.sqlite`
- 报告输出：`runtime/data/`
- 健康状态与恢复事件：`runtime/data/health/`
- 运行日志：`logs/`

初始化目录和配置：

```bash
cd ~/apps/ploymarket
scripts/setup_vps_runtime.sh
```

策略参数仍以 `config/default.toml` 为源；每次更新策略后重新运行初始化脚本，会同步最新参数并只覆盖路径到 VPS 独立目录。

VPS 专用配置还会关闭 HTTP cache 和 live market 回退：实时市场发现失败时该轮不产生开仓候选，不用旧市场池替代。
实时健康检查依据当轮返回的活跃 live BTC 市场覆盖数量，而不是与 SQLite 中不断积累的历史研究市场总量比较；否则历史样本增长会错误停止实时扫描。

## 首轮验证

先手工执行一轮，确认公开 API、数据写入和报告生成都健康：

```bash
PLOYMARKET_CONFIG=config/vps.local.toml scripts/research_cycle.sh
tail -n 40 logs/research_cycle.out.log
tail -n 40 logs/research_cycle.err.log
```

首轮结果只说明流水线可运行。需要多日、不同时段和足够交易样本后，才能评估策略是否达到进入小额实盘观察的标准。

实时模拟成交约束：

- BTC spot 每轮从 Coinbase live 请求；若最新 K 线超过 15 分钟，禁止新的方向性开仓。
- `paper-run` 的 Polymarket 历史价格每轮 live 请求，不使用 HTTP cache 或 SQLite 回退生成交易依据。
- 产生 BUY 候选后，必须读取对应 YES/NO CLOB 实时订单簿；入场以 ask 模拟，退出判断以 bid 模拟。
- 实时盘口缺失、价差超过风控阈值、或按 ask 重估后净 edge 不足时，跳过开仓。
- 每个拟 `TAKER` 候选还会写入 `execution_stress_<timestamp>.csv` 与 `shadow_order_events_<timestamp>.csv`；主 paper 路径保留实时 ask 下的基线模拟成交，压力路径单独记录延迟恶化、`FOK` 不成交与 `FAK` 部分成交。`execution_stress_report.csv` 累计汇总这些结果；系统仍不发送真实订单。

## 定时运行

安装用户级 `cron`，默认每 5 分钟运行实时模拟链、每小时运行一次深度研究链，并在每个五分钟窗口的第 2 分钟执行 watchdog：

```bash
scripts/install_research_cycle_cron.sh
crontab -l
```

实时模拟链执行 `btc-price`、`paper-run`、`paper-report`、`spread-scan` 和 `flow-scan`，通常几十秒内完成。深度研究链执行回测、对齐统计与参数扫描，耗时可能数分钟，不应阻塞实时观察。

自定义为实时每 10 分钟、深度研究每小时第 27 分钟：

```bash
scripts/install_research_cycle_cron.sh '*/10 * * * *' '27 * * * *'
```

两条链各自包含进程锁与状态文件；如果同类型上一轮仍在健康执行，新的 tick 会跳过而不是并行污染数据。

## 自动发现与恢复

每次执行会原子写入 `runtime/data/health/live_paper_cycle.json` 或 `research_cycle.json`，记录 `running`、`success`、`failed`、最后执行步骤和最后成功时间。watchdog 将恢复动作追加到 `runtime/data/health/watchdog_events.csv`。

- 实时链最后成功超过 `10` 分钟，或运行超过 `4` 分钟仍未结束，会被判定异常并重试。
- 深度链最后成功超过 `2` 小时，或运行超过 `1` 小时仍未结束，会被判定异常并重试。
- 单个实时步骤最多运行 `90` 秒，深度研究步骤最多运行 `900` 秒；超时会以失败状态退出，等待 watchdog 重试。
- `paper-run --market-type all` 若由于 Gamma/CLOB 异常没有写出任何实时市场，也会以失败退出并触发重试；不能把 `DATA_DEGRADED` 空轮记作健康采样。
- 进程异常退出留下的锁目录会被识别为遗留锁并自动移除；仍有活跃进程的锁不会强行抢占。
- 实时链状态缺失、失败或过期时，`daily-report` 强制输出 `not_ready`，不会把可能不完整的样本当成进入实盘的证据。

watchdog 能自动恢复暂时性网络失败、卡住的任务和遗留锁；持续存在的代码缺陷仍需要修复代码，而不是盲目重复模拟交易。此时状态会持续为失败并留痕，必须在恢复健康后再评价 PnL。

## 查看结果

```bash
tail -f logs/research_cycle.out.log
tail -f logs/research_cycle.err.log
tail -f logs/live_paper_cycle.out.log
tail -f logs/live_paper_cycle.err.log
tail -f logs/watchdog_cycle.out.log
tail -f logs/watchdog_cycle.err.log
cat runtime/data/health/live_paper_cycle.json
cat runtime/data/health/research_cycle.json
cat runtime/data/health/watchdog_events.csv
cat runtime/data/daily_report.csv
cat runtime/data/paper_report.csv
cat runtime/data/portfolio_mtm_summary.csv
ls -t runtime/data/execution_stress_*.csv | head -n 1 | xargs cat
cat runtime/data/execution_stress_report.csv
ls -t runtime/data/shadow_order_events_*.csv | head -n 1 | xargs cat
```

关注项目：

- `logs/research_cycle.err.log` 是否持续为空，尤其是 `IncompleteRead`、超时或订单簿 `404`。
- 两个健康 JSON 是否保持 `success` 或短时 `running`；`watchdog_events.csv` 中持续重试失败必须立即调查。
- `paper_report.csv` 中 `paper_runs` 是否稳定增加，实时扫描是否覆盖足够市场。
- `daily_report.csv` 和 `portfolio_mtm_summary.csv` 中的 `PnL` 与最大回撤是否在新样本期内稳定。
- `TAKER` 信号是否过度集中于一个市场或一个 strike。
- `execution_stress` 中候选在延迟价格恶化后是否仍通过；若基线 PnL 正但 `robust` 长期低、`NO_FILL` 或部分成交过多，说明实盘执行后收益可能消失。不要只看基线交易次数。

## 实盘边界

VPS 运行成功和短期正 `PnL` 都不足以证明可盈利。进入实盘前仍需满足：实时数据层持续健康、足够样本量、费用和滑点后仍有稳定正期望、最大回撤可承受、单市场重复开仓与停损机制经过验证，并先以极小金额灰度执行。
