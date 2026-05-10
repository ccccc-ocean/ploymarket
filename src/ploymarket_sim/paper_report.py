from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PaperRunSummary:
    run_timestamp: int
    market_count: int
    buy_yes_count: int
    hold_count: int
    avoid_count: int
    best_market_id: str
    best_market_type: str
    best_net_edge: float
    best_action: str
    best_question: str


def load_paper_run_summaries(output_dir: str) -> list[PaperRunSummary]:
    summaries = []
    for path in sorted(Path(output_dir).glob("paper_run_*.csv")):
        rows = _read_rows(path)
        if not rows:
            continue
        summaries.append(_summarize_rows(rows))
    return summaries


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _summarize_rows(rows: list[dict[str, str]]) -> PaperRunSummary:
    best = max(rows, key=lambda row: _float(row.get("net_edge")))
    return PaperRunSummary(
        run_timestamp=int(float(rows[0]["run_timestamp"])),
        market_count=len(rows),
        buy_yes_count=len([row for row in rows if row["action"] == "BUY_YES"]),
        hold_count=len([row for row in rows if row["action"] == "HOLD"]),
        avoid_count=len([row for row in rows if row["action"] == "AVOID"]),
        best_market_id=best["market_id"],
        best_market_type=best["market_type"],
        best_net_edge=_float(best.get("net_edge")),
        best_action=best["action"],
        best_question=best["question"],
    )


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0
