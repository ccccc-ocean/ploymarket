from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FilterReasonRow:
    market_type: str
    reason_bucket: str
    row_count: int
    positive_edge_count: int
    max_expected_edge: float
    example_question: str
    example_reason: str


def build_filter_reason_report(output_dir: str, recent_runs: int = 288) -> list[FilterReasonRow]:
    paths = sorted(Path(output_dir).glob("paper_run_*.csv"))[-max(1, recent_runs) :]
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for path in paths:
        for row in _read_rows(path):
            if row.get("execution_mode") != "SKIP":
                continue
            key = (row.get("market_type", "unknown"), reason_bucket(row.get("reason", "")))
            grouped.setdefault(key, []).append(row)

    rows = []
    for (market_type, bucket_name), items in grouped.items():
        positive_edge_items = [row for row in items if _float(row.get("expected_net_edge")) > 0]
        best = max(items, key=lambda row: _float(row.get("expected_net_edge")), default={})
        rows.append(
            FilterReasonRow(
                market_type=market_type,
                reason_bucket=bucket_name,
                row_count=len(items),
                positive_edge_count=len(positive_edge_items),
                max_expected_edge=_float(best.get("expected_net_edge")),
                example_question=best.get("question", ""),
                example_reason=best.get("reason", ""),
            )
        )
    return sorted(rows, key=lambda row: (row.positive_edge_count, row.max_expected_edge, row.row_count), reverse=True)


def write_filter_reason_report_csv(rows: list[FilterReasonRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "filter_reason_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_type",
                "reason_bucket",
                "row_count",
                "positive_edge_count",
                "max_expected_edge",
                "example_question",
                "example_reason",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_type,
                    row.reason_bucket,
                    row.row_count,
                    row.positive_edge_count,
                    row.max_expected_edge,
                    row.example_question,
                    row.example_reason,
                ]
            )
    return path


def print_filter_reason_report(rows: list[FilterReasonRow]) -> None:
    total_rows = sum(row.row_count for row in rows)
    total_positive_edge = sum(row.positive_edge_count for row in rows)
    print(f"filter_reason_report | skip_rows={total_rows} | positive_edge_skips={total_positive_edge}")
    for row in rows[:10]:
        print(
            f"filter_reason[{row.market_type}/{row.reason_bucket}] | rows={row.row_count} | "
            f"positive_edge={row.positive_edge_count} | max_edge={row.max_expected_edge:.4f}"
        )


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def reason_bucket(reason: str) -> str:
    if "已有模拟持仓" in reason:
        return "existing_position"
    if "当前市场类型暂不交易" in reason:
        return "observe_only_type"
    if "价格过高" in reason or "价格太接近 1" in reason or "盈亏比不足" in reason:
        return "price_too_high_or_payout_too_low"
    if "距离过远" in reason:
        return "target_too_far"
    if "正远离" in reason or "远离目标" in reason:
        return "btc_moving_away"
    if "正接近" in reason or "未明显远离" in reason or "接近/站上" in reason or "接近/跌破" in reason:
        return "btc_near_or_crossing_strike"
    if "BTC regime" in reason:
        return "btc_regime_block"
    if "实时 ask 重定价后净 edge 不足" in reason:
        return "live_reprice_edge_too_weak"
    if "净优势不足" in reason:
        return "edge_too_low"
    if "暂不允许" in reason:
        return "type_side_not_enabled"
    if "止盈后重新入场" in reason:
        return "reentry_edge_too_weak"
    if "连续止损" in reason or "触发止损" in reason or "冷却中" in reason:
        return "loss_cooldown"
    if "缺少" in reason:
        return "missing_context"
    if "短期隐含概率转弱" in reason:
        return "probability_momentum_weak"
    return "other"


_reason_bucket = reason_bucket


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0
