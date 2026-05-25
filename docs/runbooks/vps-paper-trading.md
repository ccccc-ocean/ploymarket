# VPS 模拟盘运行手册

## 目标

VPS 目前只用于实时公开行情抓取、信号、回测和 paper-run，不配置钱包、私钥或实盘下单能力。它的价值是连续积累网络更稳定的前瞻样本，而不是提前放宽实盘门槛。

## 数据隔离

仓库中的 `data/` 包含既有研究结果，不能把它与 VPS 新产生的样本直接混合作为上线依据。服务器运行时使用未提交的 `config/vps.local.toml`：

- HTTP 缓存：`runtime/cache/http/`
- SQLite 存储：`runtime/data/ploymarket.sqlite`
- 报告输出：`runtime/data/`
- 运行日志：`logs/`

初始化目录和配置：

```bash
cd ~/apps/ploymarket
scripts/setup_vps_runtime.sh
```

策略参数仍以 `config/default.toml` 为源；每次更新策略后重新运行初始化脚本，会同步最新参数并只覆盖路径到 VPS 独立目录。

## 首轮验证

先手工执行一轮，确认公开 API、数据写入和报告生成都健康：

```bash
PLOYMARKET_CONFIG=config/vps.local.toml scripts/research_cycle.sh
tail -n 40 logs/research_cycle.out.log
tail -n 40 logs/research_cycle.err.log
```

首轮结果只说明流水线可运行。需要多日、不同时段和足够交易样本后，才能评估策略是否达到进入小额实盘观察的标准。

## 定时运行

安装用户级 `cron`，默认每 10 分钟尝试运行一次：

```bash
scripts/install_research_cycle_cron.sh
crontab -l
```

自定义为每 15 分钟：

```bash
scripts/install_research_cycle_cron.sh '*/15 * * * *'
```

研究脚本含进程锁；如果完整回测超过调度间隔，新的 tick 会跳过而不是并行污染数据。

## 查看结果

```bash
tail -f logs/research_cycle.out.log
tail -f logs/research_cycle.err.log
cat runtime/data/daily_report.csv
cat runtime/data/paper_report.csv
cat runtime/data/portfolio_mtm_summary.csv
```

关注项目：

- `logs/research_cycle.err.log` 是否持续为空，尤其是 `IncompleteRead`、超时或订单簿 `404`。
- `paper_report.csv` 中 `paper_runs` 是否稳定增加，实时扫描是否覆盖足够市场。
- `daily_report.csv` 和 `portfolio_mtm_summary.csv` 中的 `PnL` 与最大回撤是否在新样本期内稳定。
- `TAKER` 信号是否过度集中于一个市场或一个 strike。

## 实盘边界

VPS 运行成功和短期正 `PnL` 都不足以证明可盈利。进入实盘前仍需满足：实时数据层持续健康、足够样本量、费用和滑点后仍有稳定正期望、最大回撤可承受、单市场重复开仓与停损机制经过验证，并先以极小金额灰度执行。
