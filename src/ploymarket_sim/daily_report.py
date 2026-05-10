from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from time import time


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
    readiness: str
    reason: str


def build_daily_report(output_dir: str) -> DailyReport:
    directory = Path(output_dir)
    paper_rows = _read_csv(directory / "paper_report.csv")
    portfolio_rows = _read_csv(directory / "portfolio_mtm_summary.csv")
    backtest_rows = _read_csv(directory / "backtest_summary_by_type.csv")
    alignment_rows = _read_csv(directory / "alignment_summary.csv")
    edge_rows = _read_csv(directory / "edge_report.csv")

    latest_paper = paper_rows[-1] if paper_rows else {}
    portfolio = portfolio_rows[0] if portfolio_rows else {}
    aggregate = _first_row(backtest_rows, "market_type", "all")
    alignment_1h = _first_row(alignment_rows, "horizon_hours", "1")

    replay_pnl = _float(portfolio.get("realized_pnl"))
    replay_max_drawdown = _float(portfolio.get("max_drawdown"))
    replay_trade_count = int(_float(aggregate.get("trade_count")))
    replay_win_rate = _float(aggregate.get("win_rate"))
    alignment_samples_1h = int(_float(alignment_1h.get("sample_count")))

    readiness, reason = _readiness(replay_pnl, replay_max_drawdown, replay_trade_count, alignment_samples_1h, len(paper_rows))

    return DailyReport(
        generated_at=int(time()),
        paper_runs=len(paper_rows),
        latest_markets=int(_float(latest_paper.get("market_count"))),
        latest_taker=int(_float(latest_paper.get("taker_count"))),
        latest_maker=int(_float(latest_paper.get("maker_count"))),
        latest_skip=int(_float(latest_paper.get("skip_count"))),
        replay_pnl=replay_pnl,
        replay_max_drawdown=replay_max_drawdown,
        replay_trade_count=replay_trade_count,
        replay_win_rate=replay_win_rate,
        alignment_samples_1h=alignment_samples_1h,
        edge_bucket_count=len(edge_rows),
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
                report.readiness,
                report.reason,
            ]
        )
    return path


def _readiness(
    replay_pnl: float,
    replay_max_drawdown: float,
    replay_trade_count: int,
    alignment_samples_1h: int,
    paper_runs: int,
) -> tuple[str, str]:
    if paper_runs < 14:
        return "not_ready", "paper-run 样本不足，至少需要连续多日/多轮观察"
    if replay_trade_count < 30:
        return "not_ready", "离线回放交易数不足，无法判断稳定性"
    if alignment_samples_1h < 10_000:
        return "not_ready", "alignment 样本不足，分层统计仍不稳"
    if replay_pnl <= 0:
        return "not_ready", "扣除成本后的离线回放仍未盈利"
    if replay_max_drawdown > 0.08:
        return "not_ready", "最大回撤超过当前保守阈值"
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
