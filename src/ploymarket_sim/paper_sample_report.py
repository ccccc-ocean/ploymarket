from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .probe_performance_report import probe_family_from_reason


@dataclass(frozen=True)
class PaperSampleRow:
    market_type: str
    recent_runs: int
    unique_market_count: int
    row_count: int
    taker_count: int
    buy_yes_taker_count: int
    buy_no_taker_count: int
    probe_taker_count: int
    skip_count: int
    positive_edge_skip_count: int
    taker_rate: float
    probe_taker_rate: float
    max_expected_edge: float
    average_taker_edge: float
    top_probe_families: str
    sample_status: str


def build_paper_sample_report(output_dir: str, recent_runs: int = 288) -> list[PaperSampleRow]:
    paths = sorted(Path(output_dir).glob("paper_run_*.csv"))[-max(1, recent_runs) :]
    grouped: dict[str, list[dict[str, str]]] = {}
    for path in paths:
        for row in _read_rows(path):
            grouped.setdefault(row.get("market_type", "unknown"), []).append(row)

    rows = []
    for market_type, items in grouped.items():
        takers = [row for row in items if row.get("execution_mode") == "TAKER"]
        buy_yes_takers = [row for row in takers if row.get("execution_side") == "BUY_YES" or row.get("action") == "BUY_YES"]
        buy_no_takers = [row for row in takers if row.get("execution_side") == "BUY_NO" or row.get("action") == "BUY_NO"]
        probe_takers = [row for row in takers if _is_probe_reason(row.get("reason", ""))]
        skips = [row for row in items if row.get("execution_mode", "SKIP") == "SKIP"]
        positive_edge_skips = [row for row in skips if _float(row.get("expected_net_edge")) > 0]
        top_probe_families = _top_probe_families(probe_takers)
        rows.append(
            PaperSampleRow(
                market_type=market_type,
                recent_runs=len(paths),
                unique_market_count=len({row.get("market_id", "") for row in items if row.get("market_id", "")}),
                row_count=len(items),
                taker_count=len(takers),
                buy_yes_taker_count=len(buy_yes_takers),
                buy_no_taker_count=len(buy_no_takers),
                probe_taker_count=len(probe_takers),
                skip_count=len(skips),
                positive_edge_skip_count=len(positive_edge_skips),
                taker_rate=len(takers) / len(items) if items else 0.0,
                probe_taker_rate=len(probe_takers) / len(takers) if takers else 0.0,
                max_expected_edge=max((_float(row.get("expected_net_edge")) for row in items), default=0.0),
                average_taker_edge=sum(_float(row.get("expected_net_edge")) for row in takers) / len(takers) if takers else 0.0,
                top_probe_families=top_probe_families,
                sample_status=_sample_status(len(takers), len(probe_takers), len(positive_edge_skips)),
            )
        )
    return sorted(rows, key=lambda row: (row.taker_count, row.max_expected_edge), reverse=True)


def write_paper_sample_report_csv(rows: list[PaperSampleRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "paper_sample_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_type",
                "recent_runs",
                "unique_market_count",
                "row_count",
                "taker_count",
                "buy_yes_taker_count",
                "buy_no_taker_count",
                "probe_taker_count",
                "skip_count",
                "positive_edge_skip_count",
                "taker_rate",
                "probe_taker_rate",
                "max_expected_edge",
                "average_taker_edge",
                "top_probe_families",
                "sample_status",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_type,
                    row.recent_runs,
                    row.unique_market_count,
                    row.row_count,
                    row.taker_count,
                    row.buy_yes_taker_count,
                    row.buy_no_taker_count,
                    row.probe_taker_count,
                    row.skip_count,
                    row.positive_edge_skip_count,
                    row.taker_rate,
                    row.probe_taker_rate,
                    row.max_expected_edge,
                    row.average_taker_edge,
                    row.top_probe_families,
                    row.sample_status,
                ]
            )
    return path


def print_paper_sample_report(rows: list[PaperSampleRow]) -> None:
    total_rows = sum(row.row_count for row in rows)
    total_takers = sum(row.taker_count for row in rows)
    total_probe_takers = sum(row.probe_taker_count for row in rows)
    total_positive_edge_skips = sum(row.positive_edge_skip_count for row in rows)
    sample_starved_types = len([row for row in rows if row.sample_status == "sample_starved"])
    print(
        f"paper_sample_report | rows={total_rows} | takers={total_takers} | "
        f"probe_takers={total_probe_takers} | positive_edge_skips={total_positive_edge_skips} | "
        f"sample_starved_types={sample_starved_types}"
    )
    for row in rows[:8]:
        print(
            f"paper_sample[{row.market_type}] | rows={row.row_count} | takers={row.taker_count} | "
            f"buy_yes={row.buy_yes_taker_count} | buy_no={row.buy_no_taker_count} | "
            f"probe_takers={row.probe_taker_count} | positive_edge_skips={row.positive_edge_skip_count} | "
            f"max_edge={row.max_expected_edge:.4f} | status={row.sample_status} | families={row.top_probe_families or 'none'}"
        )


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _is_probe_reason(reason: str) -> bool:
    return "探索仓" in reason or "挑战仓" in reason


def _top_probe_families(rows: list[dict[str, str]]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        family = probe_family_from_reason(row.get("reason", ""))
        counts[family] = counts.get(family, 0) + 1
    top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    return ";".join(f"{family}:{count}" for family, count in top)


def _sample_status(taker_count: int, probe_taker_count: int, positive_edge_skip_count: int) -> str:
    if taker_count == 0 and positive_edge_skip_count > 0:
        return "sample_starved"
    if taker_count == 0:
        return "no_edge"
    if probe_taker_count == taker_count:
        return "probe_only"
    if probe_taker_count > 0:
        return "mixed"
    return "main_strategy"


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0
