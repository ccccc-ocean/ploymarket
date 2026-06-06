from __future__ import annotations

import csv
from dataclasses import dataclass, field
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
    return list(iter_alignment_rows_csv(path))


def iter_alignment_rows_csv(path: str | Path):
    csv_path = Path(path)
    if not csv_path.exists():
        return
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            try:
                yield AlignmentRow(
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
            except (KeyError, TypeError, ValueError):
                continue


@dataclass
class _BucketAccumulator:
    count: int = 0
    yes_up_count: int = 0
    sum_yes_change: float = 0.0
    sum_btc_past_1h_return: float = 0.0
    sum_btc_future_return: float = 0.0
    yes_changes: list[float] = field(default_factory=list)

    def add(self, row: AlignmentRow) -> None:
        self.count += 1
        self.yes_up_count += 1 if row.yes_change > 0 else 0
        self.sum_yes_change += row.yes_change
        self.sum_btc_past_1h_return += row.btc_past_1h_return
        self.sum_btc_future_return += row.btc_return
        self.yes_changes.append(row.yes_change)


def build_edge_buckets(rows: list[AlignmentRow], min_samples: int = 30) -> list[EdgeBucket]:
    grouped: dict[tuple[int, str, str], _BucketAccumulator] = {}
    for row in rows:
        key = (row.horizon_hours, yes_price_bucket(row.yes_price), btc_return_bucket(row.btc_past_1h_return))
        grouped.setdefault(key, _BucketAccumulator()).add(row)

    return _build_edge_buckets_from_accumulators(grouped, min_samples=min_samples)


def build_edge_buckets_from_csv(path: str | Path, min_samples: int = 30) -> list[EdgeBucket]:
    grouped: dict[tuple[int, str, str], _BucketAccumulator] = {}
    for row in iter_alignment_rows_csv(path):
        key = (row.horizon_hours, yes_price_bucket(row.yes_price), btc_return_bucket(row.btc_past_1h_return))
        grouped.setdefault(key, _BucketAccumulator()).add(row)
    return _build_edge_buckets_from_accumulators(grouped, min_samples=min_samples)


def _build_edge_buckets_from_accumulators(
    grouped: dict[tuple[int, str, str], _BucketAccumulator],
    min_samples: int,
) -> list[EdgeBucket]:
    buckets = []
    for (horizon, yes_bucket, btc_past_1h_bucket), bucket in grouped.items():
        if bucket.count < min_samples:
            continue
        yes_changes = sorted(bucket.yes_changes)
        median = _median(yes_changes)
        buckets.append(
            EdgeBucket(
                horizon_hours=horizon,
                yes_price_bucket=yes_bucket,
                btc_past_1h_bucket=btc_past_1h_bucket,
                sample_count=bucket.count,
                average_yes_change=bucket.sum_yes_change / bucket.count,
                median_yes_change=median,
                yes_up_rate=bucket.yes_up_count / bucket.count,
                average_btc_past_1h_return=bucket.sum_btc_past_1h_return / bucket.count,
                average_btc_future_return=bucket.sum_btc_future_return / bucket.count,
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
