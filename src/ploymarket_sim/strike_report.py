from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .market_rules import extract_usd_strike


@dataclass(frozen=True)
class StrikeReportRow:
    strike: float
    market_count: int
    traded_market_count: int
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    realized_pnl: float
    total_fees: float
    total_slippage: float
    average_pnl_per_trade: float


def build_strike_report(summary_path: str | Path) -> list[StrikeReportRow]:
    csv_path = Path(summary_path)
    if not csv_path.exists():
        return []

    buckets: dict[float, dict[str, float]] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row.get("market_type") != "price_range_daily":
                continue
            strike = extract_usd_strike(row.get("question", ""))
            if strike is None:
                continue
            bucket = buckets.setdefault(
                strike,
                {
                    "market_count": 0,
                    "traded_market_count": 0,
                    "trade_count": 0,
                    "win_count": 0,
                    "loss_count": 0,
                    "realized_pnl": 0.0,
                    "total_fees": 0.0,
                    "total_slippage": 0.0,
                },
            )
            entry_count = int(float(row.get("entry_count") or 0))
            bucket["market_count"] += 1
            bucket["traded_market_count"] += 1 if entry_count > 0 else 0
            bucket["trade_count"] += int(float(row.get("trade_count") or 0))
            bucket["win_count"] += int(float(row.get("win_count") or 0))
            bucket["loss_count"] += int(float(row.get("loss_count") or 0))
            bucket["realized_pnl"] += float(row.get("realized_pnl") or 0.0)
            bucket["total_fees"] += float(row.get("total_fees") or 0.0)
            bucket["total_slippage"] += float(row.get("total_slippage") or 0.0)

    rows = []
    for strike, bucket in sorted(buckets.items()):
        exits = bucket["win_count"] + bucket["loss_count"]
        rows.append(
            StrikeReportRow(
                strike=strike,
                market_count=int(bucket["market_count"]),
                traded_market_count=int(bucket["traded_market_count"]),
                trade_count=int(bucket["trade_count"]),
                win_count=int(bucket["win_count"]),
                loss_count=int(bucket["loss_count"]),
                win_rate=_ratio(bucket["win_count"], exits),
                realized_pnl=bucket["realized_pnl"],
                total_fees=bucket["total_fees"],
                total_slippage=bucket["total_slippage"],
                average_pnl_per_trade=_ratio(bucket["realized_pnl"], exits),
            )
        )
    return rows


def write_strike_report_csv(rows: list[StrikeReportRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "strike_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "strike",
                "market_count",
                "traded_market_count",
                "trade_count",
                "win_count",
                "loss_count",
                "win_rate",
                "realized_pnl",
                "total_fees",
                "total_slippage",
                "average_pnl_per_trade",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.strike,
                    row.market_count,
                    row.traded_market_count,
                    row.trade_count,
                    row.win_count,
                    row.loss_count,
                    row.win_rate,
                    row.realized_pnl,
                    row.total_fees,
                    row.total_slippage,
                    row.average_pnl_per_trade,
                ]
            )
    return path


def print_strike_report(rows: list[StrikeReportRow], path: Path) -> None:
    if not rows:
        print(f"strike_report | rows=0 | {path}")
        return
    traded = [row for row in rows if row.trade_count > 0]
    if not traded:
        print(f"strike_report | rows={len(rows)} | traded=0 | {path}")
        return
    best = max(traded, key=lambda row: row.realized_pnl)
    worst = min(traded, key=lambda row: row.realized_pnl)
    print(
        "strike_report | "
        f"rows={len(rows)} | best={best.strike:.0f} pnl={best.realized_pnl:.2f} trades={best.trade_count} | "
        f"worst={worst.strike:.0f} pnl={worst.realized_pnl:.2f} trades={worst.trade_count} | {path}"
    )


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
