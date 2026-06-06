from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .filter_reason_report import reason_bucket


@dataclass(frozen=True)
class BlockedEdgeRow:
    market_type: str
    market_id: str
    reason_bucket: str
    positive_edge_skip_count: int
    max_expected_edge: float
    average_positive_edge: float
    first_run_timestamp: int
    last_run_timestamp: int
    taker_count_for_market: int
    taker_sides_for_market: str
    latest_yes_price: float
    example_question: str
    example_reason: str


def build_blocked_edge_report(output_dir: str, recent_runs: int = 288) -> list[BlockedEdgeRow]:
    paths = sorted(Path(output_dir).glob("paper_run_*.csv"))[-max(1, recent_runs) :]
    market_takers: dict[str, list[dict[str, str]]] = {}
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for path in paths:
        for row in _read_rows(path):
            market_id = row.get("market_id", "")
            if row.get("execution_mode") == "TAKER":
                market_takers.setdefault(market_id, []).append(row)
                continue
            if row.get("execution_mode") != "SKIP":
                continue
            if _float(row.get("expected_net_edge")) <= 0:
                continue
            bucket = reason_bucket(row.get("reason", ""))
            key = (row.get("market_type", "unknown"), market_id, bucket)
            grouped.setdefault(key, []).append(row)

    rows = []
    for (market_type, market_id, bucket), items in grouped.items():
        positive_edges = [_float(row.get("expected_net_edge")) for row in items]
        best = max(items, key=lambda row: _float(row.get("expected_net_edge")), default={})
        latest = max(items, key=lambda row: _int(row.get("run_timestamp")), default={})
        takers = market_takers.get(market_id, [])
        rows.append(
            BlockedEdgeRow(
                market_type=market_type,
                market_id=market_id,
                reason_bucket=bucket,
                positive_edge_skip_count=len(items),
                max_expected_edge=max(positive_edges, default=0.0),
                average_positive_edge=sum(positive_edges) / len(positive_edges) if positive_edges else 0.0,
                first_run_timestamp=min((_int(row.get("run_timestamp")) for row in items), default=0),
                last_run_timestamp=max((_int(row.get("run_timestamp")) for row in items), default=0),
                taker_count_for_market=len(takers),
                taker_sides_for_market=_taker_sides(takers),
                latest_yes_price=_float(latest.get("yes_price")),
                example_question=best.get("question", ""),
                example_reason=best.get("reason", ""),
            )
        )
    return sorted(
        rows,
        key=lambda row: (row.taker_count_for_market == 0, row.positive_edge_skip_count, row.max_expected_edge),
        reverse=True,
    )


def write_blocked_edge_report_csv(rows: list[BlockedEdgeRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "blocked_edge_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_type",
                "market_id",
                "reason_bucket",
                "positive_edge_skip_count",
                "max_expected_edge",
                "average_positive_edge",
                "first_run_timestamp",
                "last_run_timestamp",
                "taker_count_for_market",
                "taker_sides_for_market",
                "latest_yes_price",
                "example_question",
                "example_reason",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_type,
                    row.market_id,
                    row.reason_bucket,
                    row.positive_edge_skip_count,
                    row.max_expected_edge,
                    row.average_positive_edge,
                    row.first_run_timestamp,
                    row.last_run_timestamp,
                    row.taker_count_for_market,
                    row.taker_sides_for_market,
                    row.latest_yes_price,
                    row.example_question,
                    row.example_reason,
                ]
            )
    return path


def print_blocked_edge_report(rows: list[BlockedEdgeRow]) -> None:
    total_positive_edge_skips = sum(row.positive_edge_skip_count for row in rows)
    unresolved_rows = len([row for row in rows if row.taker_count_for_market == 0])
    print(
        f"blocked_edge_report | rows={len(rows)} | positive_edge_skips={total_positive_edge_skips} | "
        f"without_later_taker={unresolved_rows}"
    )
    for row in rows[:12]:
        taker_label = row.taker_sides_for_market or "none"
        print(
            f"blocked_edge[{row.market_type}/{row.reason_bucket}] | market={row.market_id} | "
            f"skips={row.positive_edge_skip_count} | max_edge={row.max_expected_edge:.4f} | "
            f"avg_edge={row.average_positive_edge:.4f} | takers={row.taker_count_for_market}:{taker_label} | "
            f"latest_yes={row.latest_yes_price:.3f}"
        )


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _taker_sides(rows: list[dict[str, str]]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        side = row.get("execution_side") or row.get("action") or "UNKNOWN"
        counts[side] = counts.get(side, 0) + 1
    return ";".join(f"{side}:{count}" for side, count in sorted(counts.items()))


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0


def _int(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0
