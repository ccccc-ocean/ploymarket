from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .alignment import AlignmentRow


@dataclass(frozen=True)
class EdgeBucket:
    horizon_hours: int
    yes_price_bucket: str
    btc_past_1h_bucket: str
    sample_count: int
    average_yes_change: float
    median_yes_change: float
    yes_up_rate: float
    average_btc_past_1h_return: float
    average_btc_future_return: float


def load_alignment_rows_csv(path: str | Path) -> list[AlignmentRow]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        rows = []
        for row in csv.DictReader(file):
            try:
                rows.append(
                    AlignmentRow(
                        market_id=str(row["market_id"]),
                        question=str(row.get("question", "")),
                        timestamp=int(float(row["timestamp"])),
                        horizon_hours=int(float(row["horizon_hours"])),
                        yes_price=float(row["yes_price"]),
                        future_yes_price=float(row["future_yes_price"]),
                        yes_change=float(row["yes_change"]),
                        btc_close=float(row["btc_close"]),
                        future_btc_close=float(row["future_btc_close"]),
                        btc_return=float(row["btc_return"]),
                        btc_past_1h_return=float(row.get("btc_past_1h_return", 0.0)),
                        btc_past_3h_return=float(row.get("btc_past_3h_return", 0.0)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return rows


def build_edge_buckets(rows: list[AlignmentRow], min_samples: int = 30) -> list[EdgeBucket]:
    grouped: dict[tuple[int, str, str], list[AlignmentRow]] = {}
    for row in rows:
        key = (row.horizon_hours, yes_price_bucket(row.yes_price), btc_return_bucket(row.btc_past_1h_return))
        grouped.setdefault(key, []).append(row)

    buckets = []
    for (horizon, yes_bucket, btc_past_1h_bucket), bucket_rows in grouped.items():
        if len(bucket_rows) < min_samples:
            continue
        yes_changes = sorted(row.yes_change for row in bucket_rows)
        median = _median(yes_changes)
        buckets.append(
            EdgeBucket(
                horizon_hours=horizon,
                yes_price_bucket=yes_bucket,
                btc_past_1h_bucket=btc_past_1h_bucket,
                sample_count=len(bucket_rows),
                average_yes_change=sum(yes_changes) / len(yes_changes),
                median_yes_change=median,
                yes_up_rate=len([value for value in yes_changes if value > 0]) / len(yes_changes),
                average_btc_past_1h_return=sum(row.btc_past_1h_return for row in bucket_rows) / len(bucket_rows),
                average_btc_future_return=sum(row.btc_return for row in bucket_rows) / len(bucket_rows),
            )
        )
    return sorted(buckets, key=lambda item: (item.horizon_hours, item.yes_price_bucket, item.btc_past_1h_bucket))


def yes_price_bucket(price: float) -> str:
    if price < 0.03:
        return "00_lt_0.03"
    if price < 0.08:
        return "01_0.03_0.08"
    if price < 0.20:
        return "02_0.08_0.20"
    if price < 0.50:
        return "03_0.20_0.50"
    return "04_gte_0.50"


def btc_return_bucket(value: float) -> str:
    if value <= -0.01:
        return "00_btc_down_gt_1pct"
    if value < -0.0025:
        return "01_btc_down_0.25_1pct"
    if value <= 0.0025:
        return "02_btc_flat"
    if value < 0.01:
        return "03_btc_up_0.25_1pct"
    return "04_btc_up_gt_1pct"


def _median(values: list[float]) -> float:
    midpoint = len(values) // 2
    if len(values) % 2:
        return values[midpoint]
    return (values[midpoint - 1] + values[midpoint]) / 2
