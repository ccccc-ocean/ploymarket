from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PaperRunSummary:
    run_timestamp: int
    market_count: int
    buy_yes_count: int
    buy_no_count: int
    hold_count: int
    avoid_count: int
    taker_count: int
    maker_count: int
    skip_count: int
    best_market_id: str
    best_market_type: str
    best_net_edge: float
    best_action: str
    best_execution_mode: str
    best_question: str


def load_paper_run_summaries(output_dir: str) -> list[PaperRunSummary]:
    summaries = []
    for path in sorted(Path(output_dir).glob("paper_run_*.csv")):
        rows = _read_rows(path)
        if not rows:
            summaries.append(_empty_summary(path))
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
        buy_no_count=len([row for row in rows if row["action"] == "BUY_NO"]),
        hold_count=len([row for row in rows if row["action"] == "HOLD"]),
        avoid_count=len([row for row in rows if row["action"] == "AVOID"]),
        taker_count=len([row for row in rows if row.get("execution_mode") == "TAKER"]),
        maker_count=len([row for row in rows if row.get("execution_mode") == "MAKER"]),
        skip_count=len([row for row in rows if row.get("execution_mode", "SKIP") == "SKIP"]),
        best_market_id=best["market_id"],
        best_market_type=best["market_type"],
        best_net_edge=_float(best.get("net_edge")),
        best_action=best["action"],
        best_execution_mode=best.get("execution_mode", "UNKNOWN"),
        best_question=best["question"],
    )


def _empty_summary(path: Path) -> PaperRunSummary:
    return PaperRunSummary(
        run_timestamp=_timestamp_from_path(path),
        market_count=0,
        buy_yes_count=0,
        buy_no_count=0,
        hold_count=0,
        avoid_count=0,
        taker_count=0,
        maker_count=0,
        skip_count=0,
        best_market_id="",
        best_market_type="",
        best_net_edge=0.0,
        best_action="DATA_DEGRADED",
        best_execution_mode="SKIP",
        best_question="live market data unavailable; local cache not used for realtime paper-run",
    )


def _timestamp_from_path(path: Path) -> int:
    try:
        return int(path.stem.replace("paper_run_", ""))
    except ValueError:
        return 0


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0
