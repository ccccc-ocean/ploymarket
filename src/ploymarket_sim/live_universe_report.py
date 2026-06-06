from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .classifier import MARKET_TYPES, classify_market
from .paper_sample_report import PaperSampleRow


@dataclass(frozen=True)
class LiveUniverseRow:
    market_type: str
    live_count: int
    sample_status: str
    recent_taker_count: int
    positive_edge_skip_count: int
    universe_status: str


def build_live_universe_report(markets, sample_rows: list[PaperSampleRow]) -> list[LiveUniverseRow]:
    live_counts = Counter(classify_market(market).market_type for market in markets)
    samples_by_type = {row.market_type: row for row in sample_rows}
    rows = []
    for market_type in MARKET_TYPES:
        sample = samples_by_type.get(market_type)
        live_count = live_counts.get(market_type, 0)
        sample_status = "" if sample is None else sample.sample_status
        recent_taker_count = 0 if sample is None else sample.taker_count
        positive_edge_skip_count = 0 if sample is None else sample.positive_edge_skip_count
        rows.append(
            LiveUniverseRow(
                market_type=market_type,
                live_count=live_count,
                sample_status=sample_status,
                recent_taker_count=recent_taker_count,
                positive_edge_skip_count=positive_edge_skip_count,
                universe_status=_universe_status(live_count, sample_status, positive_edge_skip_count),
            )
        )
    return sorted(rows, key=lambda row: (row.live_count, row.positive_edge_skip_count, row.recent_taker_count), reverse=True)


def write_live_universe_report_csv(rows: list[LiveUniverseRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "live_universe_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_type",
                "live_count",
                "sample_status",
                "recent_taker_count",
                "positive_edge_skip_count",
                "universe_status",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_type,
                    row.live_count,
                    row.sample_status,
                    row.recent_taker_count,
                    row.positive_edge_skip_count,
                    row.universe_status,
                ]
            )
    return path


def print_live_universe_report(rows: list[LiveUniverseRow]) -> None:
    no_live = len([row for row in rows if row.universe_status == "no_live_markets"])
    sample_starved_with_live = len([row for row in rows if row.universe_status == "sample_starved_with_live_markets"])
    print(
        f"live_universe_report | types={len(rows)} | no_live_types={no_live} | "
        f"sample_starved_with_live={sample_starved_with_live}"
    )
    for row in rows:
        print(
            f"live_universe[{row.market_type}] | live={row.live_count} | sample_status={row.sample_status or 'none'} | "
            f"takers={row.recent_taker_count} | positive_edge_skips={row.positive_edge_skip_count} | "
            f"status={row.universe_status}"
        )


def _universe_status(live_count: int, sample_status: str, positive_edge_skip_count: int) -> str:
    if live_count == 0:
        return "no_live_markets"
    if sample_status == "sample_starved":
        return "sample_starved_with_live_markets"
    if live_count > 0 and positive_edge_skip_count > 0:
        return "live_with_blocked_edge"
    return "live_available"
