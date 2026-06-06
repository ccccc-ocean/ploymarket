from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


MAIN_ACTIVE_MARKET_TYPES = {"up_down_short_term", "above_below_expiry", "touch_above"}


@dataclass(frozen=True)
class ObservationReportRow:
    market_type: str
    observed_rows: int
    hold_count: int
    avoid_count: int
    buy_yes_count: int
    buy_no_count: int
    positive_edge_count: int
    strong_edge_count: int
    best_net_edge: float
    avg_positive_net_edge: float
    replay_trade_count: int
    replay_pnl: float
    replay_max_drawdown: float
    status: str
    top_reason: str


def build_observation_report(output_dir: str, recent_runs: int = 288) -> list[ObservationReportRow]:
    directory = Path(output_dir)
    paper_rows = _load_recent_paper_rows(directory, recent_runs)
    replay_by_type = _load_replay_by_type(directory / "backtest_summary_by_type.csv")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in paper_rows:
        market_type = row.get("market_type", "")
        if market_type and market_type != "all":
            grouped[market_type].append(row)
    for market_type in replay_by_type:
        if market_type != "all":
            grouped.setdefault(market_type, [])

    rows = []
    for market_type in sorted(grouped):
        observations = grouped[market_type]
        edges = [_float(row.get("net_edge")) for row in observations]
        positive_edges = [edge for edge in edges if edge > 0]
        replay = replay_by_type.get(market_type, {})
        replay_trade_count = int(_float(replay.get("trade_count")))
        replay_pnl = _float(replay.get("pnl") or replay.get("realized_pnl"))
        replay_max_drawdown = _float(replay.get("max_drawdown"))
        rows.append(
            ObservationReportRow(
                market_type=market_type,
                observed_rows=len(observations),
                hold_count=sum(1 for row in observations if row.get("action") == "HOLD"),
                avoid_count=sum(1 for row in observations if row.get("action") == "AVOID"),
                buy_yes_count=sum(1 for row in observations if row.get("action") == "BUY_YES"),
                buy_no_count=sum(1 for row in observations if row.get("action") == "BUY_NO"),
                positive_edge_count=len(positive_edges),
                strong_edge_count=sum(1 for edge in edges if edge >= 0.01),
                best_net_edge=max(edges, default=0.0),
                avg_positive_net_edge=sum(positive_edges) / len(positive_edges) if positive_edges else 0.0,
                replay_trade_count=replay_trade_count,
                replay_pnl=replay_pnl,
                replay_max_drawdown=replay_max_drawdown,
                status=_status(
                    market_type,
                    len(observations),
                    len(positive_edges),
                    replay_trade_count,
                    replay_pnl,
                    replay_max_drawdown,
                    max(edges, default=0.0),
                ),
                top_reason=_top_reason(observations),
            )
        )
    return rows


def write_observation_report_csv(rows: list[ObservationReportRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "observation_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_type",
                "observed_rows",
                "hold_count",
                "avoid_count",
                "buy_yes_count",
                "buy_no_count",
                "positive_edge_count",
                "strong_edge_count",
                "best_net_edge",
                "avg_positive_net_edge",
                "replay_trade_count",
                "replay_pnl",
                "replay_max_drawdown",
                "status",
                "top_reason",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_type,
                    row.observed_rows,
                    row.hold_count,
                    row.avoid_count,
                    row.buy_yes_count,
                    row.buy_no_count,
                    row.positive_edge_count,
                    row.strong_edge_count,
                    row.best_net_edge,
                    row.avg_positive_net_edge,
                    row.replay_trade_count,
                    row.replay_pnl,
                    row.replay_max_drawdown,
                    row.status,
                    row.top_reason,
                ]
            )
    return path


def print_observation_report(rows: list[ObservationReportRow], path: Path) -> None:
    if not rows:
        print(f"observation_report | rows=0 | {path}")
        return
    candidates = [row for row in rows if row.status == "promotion_candidate"]
    blocked = [row for row in rows if row.status == "blocked_research"]
    best = max(rows, key=lambda row: (row.replay_pnl, row.best_net_edge))
    print(
        f"observation_report | rows={len(rows)} | promotion_candidates={len(candidates)} | "
        f"blocked={len(blocked)} | best={best.market_type} pnl={best.replay_pnl:.2f} "
        f"trades={best.replay_trade_count} status={best.status} | {path}"
    )


def _load_recent_paper_rows(directory: Path, recent_runs: int) -> list[dict[str, str]]:
    paths = sorted(directory.glob("paper_run_*.csv"))
    if recent_runs > 0:
        paths = paths[-recent_runs:]
    rows = []
    for path in paths:
        with path.open("r", newline="", encoding="utf-8") as file:
            rows.extend(csv.DictReader(file))
    return rows


def _load_replay_by_type(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", newline="", encoding="utf-8") as file:
        return {row.get("market_type", ""): row for row in csv.DictReader(file) if row.get("market_type")}


def _top_reason(rows: list[dict[str, str]]) -> str:
    reasons = Counter(row.get("reason", "") for row in rows if row.get("reason"))
    if not reasons:
        return ""
    reason, count = reasons.most_common(1)[0]
    return f"{reason} ({count})"


def _status(
    market_type: str,
    observed_rows: int,
    positive_edge_count: int,
    replay_trade_count: int,
    replay_pnl: float,
    replay_max_drawdown: float,
    best_net_edge: float,
) -> str:
    if market_type in MAIN_ACTIVE_MARKET_TYPES and replay_trade_count > 0 and replay_pnl > 0:
        return "main_active"
    if replay_trade_count > 0 and (replay_pnl < 0 or replay_max_drawdown > 0.12):
        return "blocked_research"
    if (
        observed_rows >= 50
        and positive_edge_count >= 10
        and replay_trade_count >= 4
        and replay_pnl > 0
        and replay_max_drawdown <= 0.10
        and best_net_edge >= 0.01
    ):
        return "promotion_candidate"
    if observed_rows >= 50:
        return "observe_optimize"
    return "collect_more_samples"


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0
