from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from time import time

from .pipeline_health import assess_health, load_state


@dataclass(frozen=True)
class DailyReport:
    generated_at: int
    paper_runs: int
    latest_markets: int
    latest_taker: int
    latest_maker: int
    latest_skip: int
    replay_pnl: float
    replay_max_drawdown: float
    replay_trade_count: int
    replay_win_rate: float
    alignment_samples_1h: int
    edge_bucket_count: int
    spread_buy_both_count: int
    spread_sell_both_count: int
    spread_best_buy_edge: float
    spread_best_sell_edge: float
    live_pipeline_healthy: bool
    live_pipeline_reason: str
    readiness: str
    reason: str


def build_daily_report(output_dir: str, readiness_max_drawdown_pct: float = 0.08) -> DailyReport:
    directory = Path(output_dir)
    paper_rows = _read_csv(directory / "paper_report.csv")
    portfolio_rows = _read_csv(directory / "portfolio_mtm_summary.csv")
    backtest_rows = _read_csv(directory / "backtest_summary_by_type.csv")
    alignment_rows = _read_csv(directory / "alignment_summary.csv")
    edge_rows = _read_csv(directory / "edge_report.csv")
    spread_rows = _read_csv(directory / "spread_scan.csv")

    latest_paper = paper_rows[-1] if paper_rows else {}
    portfolio = portfolio_rows[0] if portfolio_rows else {}
    aggregate = _first_row(backtest_rows, "market_type", "all")
    alignment_1h = _first_row(alignment_rows, "horizon_hours", "1")

    replay_pnl = _float(portfolio.get("realized_pnl"))
    replay_max_drawdown = _float(portfolio.get("max_drawdown"))
    replay_trade_count = int(_float(aggregate.get("trade_count")))
    replay_win_rate = _float(aggregate.get("win_rate"))
    alignment_samples_1h = int(_float(alignment_1h.get("sample_count")))
    spread_buy_both_count = len([row for row in spread_rows if row.get("recommendation") == "BUY_BOTH"])
    spread_sell_both_count = len([row for row in spread_rows if row.get("recommendation") == "SELL_BOTH"])
    spread_best_buy_edge = _max_float(spread_rows, "buy_pair_edge")
    spread_best_sell_edge = _max_float(spread_rows, "sell_pair_edge")
    generated_at = int(time())
    live_health = assess_health(
        load_state(directory / "health", "live_paper_cycle"),
        generated_at,
        max_success_age_seconds=600,
        max_running_age_seconds=240,
    )

    latest_markets = int(_float(latest_paper.get("market_count")))
    readiness, reason = _readiness(
        live_health.healthy,
        live_health.reason,
        replay_pnl,
        replay_max_drawdown,
        replay_trade_count,
        alignment_samples_1h,
        len(paper_rows),
        latest_markets,
        readiness_max_drawdown_pct,
    )

    return DailyReport(
        generated_at=generated_at,
        paper_runs=len(paper_rows),
        latest_markets=latest_markets,
        latest_taker=int(_float(latest_paper.get("taker_count"))),
        latest_maker=int(_float(latest_paper.get("maker_count"))),
        latest_skip=int(_float(latest_paper.get("skip_count"))),
        replay_pnl=replay_pnl,
        replay_max_drawdown=replay_max_drawdown,
        replay_trade_count=replay_trade_count,
        replay_win_rate=replay_win_rate,
        alignment_samples_1h=alignment_samples_1h,
        edge_bucket_count=len(edge_rows),
        spread_buy_both_count=spread_buy_both_count,
        spread_sell_both_count=spread_sell_both_count,
        spread_best_buy_edge=spread_best_buy_edge,
        spread_best_sell_edge=spread_best_sell_edge,
        live_pipeline_healthy=live_health.healthy,
        live_pipeline_reason=live_health.reason,
        readiness=readiness,
        reason=reason,
    )


def write_daily_report_csv(report: DailyReport, output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "daily_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "generated_at",
                "paper_runs",
                "latest_markets",
                "latest_taker",
                "latest_maker",
                "latest_skip",
                "replay_pnl",
                "replay_max_drawdown",
                "replay_trade_count",
                "replay_win_rate",
                "alignment_samples_1h",
                "edge_bucket_count",
                "spread_buy_both_count",
                "spread_sell_both_count",
                "spread_best_buy_edge",
                "spread_best_sell_edge",
                "live_pipeline_healthy",
                "live_pipeline_reason",
                "readiness",
                "reason",
            ]
        )
        writer.writerow(
            [
                report.generated_at,
                report.paper_runs,
                report.latest_markets,
                report.latest_taker,
                report.latest_maker,
                report.latest_skip,
                report.replay_pnl,
                report.replay_max_drawdown,
                report.replay_trade_count,
                report.replay_win_rate,
                report.alignment_samples_1h,
                report.edge_bucket_count,
                report.spread_buy_both_count,
                report.spread_sell_both_count,
                report.spread_best_buy_edge,
                report.spread_best_sell_edge,
                report.live_pipeline_healthy,
                report.live_pipeline_reason,
                report.readiness,
                report.reason,
            ]
        )
    return path


def _readiness(
    live_pipeline_healthy: bool,
    live_pipeline_reason: str,
    replay_pnl: float,
    replay_max_drawdown: float,
    replay_trade_count: int,
    alignment_samples_1h: int,
    paper_runs: int,
    latest_markets: int,
    readiness_max_drawdown_pct: float,
) -> tuple[str, str]:
    if not live_pipeline_healthy:
        return "not_ready", f"实时模拟链路不健康（{live_pipeline_reason}），禁止进入实盘判断"
    if latest_markets == 0:
        return "not_ready", "最新 paper-run 没有实时市场数据，禁止把本地缓存当作实盘依据"
    if paper_runs < 14:
        return "not_ready", "paper-run 样本不足，至少需要连续多日/多轮观察"
    if replay_trade_count < 30:
        return "not_ready", "离线回放交易数不足，无法判断稳定性"
    if alignment_samples_1h < 10_000:
        return "not_ready", "alignment 样本不足，分层统计仍不稳"
    if replay_pnl <= 0:
        return "not_ready", "扣除成本后的离线回放仍未盈利"
    if replay_max_drawdown > readiness_max_drawdown_pct:
        return "not_ready", f"最大回撤超过当前观察阈值 {readiness_max_drawdown_pct:.1%}"
    return "candidate", "满足最低研究门槛，但仍需小资金实盘前检查"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _first_row(rows: list[dict[str, str]], key: str, value: str) -> dict[str, str]:
    for row in rows:
        if row.get(key) == value:
            return row
    return {}


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0


def _max_float(rows: list[dict[str, str]], key: str) -> float:
    values = [_float(row.get(key)) for row in rows if row.get(key)]
    return max(values) if values else 0.0
