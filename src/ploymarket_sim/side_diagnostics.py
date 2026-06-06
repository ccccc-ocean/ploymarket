from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


ENTRY_ACTIONS = {"BUY_YES": "YES", "MAKER_BUY_YES": "YES", "BUY_NO": "NO"}
EXIT_ACTIONS = {"SELL_YES": "YES", "SELL_NO": "NO"}


@dataclass(frozen=True)
class SideDiagnosticRow:
    market_type: str
    side: str
    market_count: int
    entry_count: int
    exit_count: int
    win_count: int
    loss_count: int
    win_rate: float
    realized_pnl: float
    total_fees: float
    total_slippage: float
    average_entry_edge: float
    worst_trade_pnl: float
    status: str
    top_loss_reason: str


def build_side_diagnostics(output_dir: str) -> list[SideDiagnosticRow]:
    directory = Path(output_dir)
    market_types = _load_market_types(directory / "backtest_summary.csv")
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    market_ids_by_key: dict[tuple[str, str], set[str]] = defaultdict(set)

    for path in sorted(directory.glob("backtest_*.csv")):
        market_id = path.stem.replace("backtest_", "")
        if market_id in {"summary", "summary_by_type"}:
            continue
        market_type = market_types.get(market_id, "unknown")
        open_side = ""
        with path.open("r", newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                action = row.get("action", "")
                side = ENTRY_ACTIONS.get(action) or EXIT_ACTIONS.get(action)
                if action == "MARK_TO_MARKET_EXIT":
                    side = open_side or "UNKNOWN"
                if not side:
                    continue
                key = (market_type, side)
                grouped[key].append(row)
                market_ids_by_key[key].add(market_id)
                if action in ENTRY_ACTIONS:
                    open_side = side
                elif action in EXIT_ACTIONS or action == "MARK_TO_MARKET_EXIT":
                    open_side = ""

    rows = []
    for (market_type, side), trades in sorted(grouped.items()):
        entries = [trade for trade in trades if trade.get("action") in ENTRY_ACTIONS]
        exits = [trade for trade in trades if trade.get("action") in EXIT_ACTIONS or trade.get("action") == "MARK_TO_MARKET_EXIT"]
        wins = [trade for trade in exits if _float(trade.get("pnl")) > 0]
        losses = [trade for trade in exits if _float(trade.get("pnl")) < 0]
        pnl = sum(_float(trade.get("pnl")) for trade in exits)
        avg_edge = _ratio(sum(_float(trade.get("net_edge")) for trade in entries), len(entries))
        rows.append(
            SideDiagnosticRow(
                market_type=market_type,
                side=side,
                market_count=len(market_ids_by_key[(market_type, side)]),
                entry_count=len(entries),
                exit_count=len(exits),
                win_count=len(wins),
                loss_count=len(losses),
                win_rate=_ratio(len(wins), len(wins) + len(losses)),
                realized_pnl=pnl,
                total_fees=sum(_float(trade.get("fee")) for trade in trades),
                total_slippage=sum(_float(trade.get("slippage")) for trade in trades),
                average_entry_edge=avg_edge,
                worst_trade_pnl=min((_float(trade.get("pnl")) for trade in exits), default=0.0),
                status=_status(len(entries), pnl, len(wins), len(losses), avg_edge),
                top_loss_reason=_top_loss_reason(losses),
            )
        )
    return rows


def write_side_diagnostics_csv(rows: list[SideDiagnosticRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "side_diagnostics.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_type",
                "side",
                "market_count",
                "entry_count",
                "exit_count",
                "win_count",
                "loss_count",
                "win_rate",
                "realized_pnl",
                "total_fees",
                "total_slippage",
                "average_entry_edge",
                "worst_trade_pnl",
                "status",
                "top_loss_reason",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_type,
                    row.side,
                    row.market_count,
                    row.entry_count,
                    row.exit_count,
                    row.win_count,
                    row.loss_count,
                    row.win_rate,
                    row.realized_pnl,
                    row.total_fees,
                    row.total_slippage,
                    row.average_entry_edge,
                    row.worst_trade_pnl,
                    row.status,
                    row.top_loss_reason,
                ]
            )
    return path


def print_side_diagnostics(rows: list[SideDiagnosticRow], path: Path) -> None:
    if not rows:
        print(f"side_diagnostics | rows=0 | {path}")
        return
    worst = min(rows, key=lambda row: row.realized_pnl)
    best = max(rows, key=lambda row: row.realized_pnl)
    print(
        f"side_diagnostics | rows={len(rows)} | best={best.market_type}/{best.side} "
        f"pnl={best.realized_pnl:.2f} entries={best.entry_count} | worst={worst.market_type}/{worst.side} "
        f"pnl={worst.realized_pnl:.2f} entries={worst.entry_count} status={worst.status} | {path}"
    )


def _load_market_types(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", newline="", encoding="utf-8") as file:
        return {row.get("market_id", ""): row.get("market_type", "unknown") for row in csv.DictReader(file)}


def _top_loss_reason(losses: list[dict[str, str]]) -> str:
    reasons = Counter(row.get("reason", "") for row in losses if row.get("reason"))
    if not reasons:
        return ""
    reason, count = reasons.most_common(1)[0]
    return f"{reason} ({count})"


def _status(entry_count: int, pnl: float, win_count: int, loss_count: int, average_entry_edge: float) -> str:
    if entry_count < 4:
        return "collect_more_samples"
    if pnl > 0 and win_count >= loss_count and average_entry_edge > 0:
        return "side_candidate"
    if pnl < 0 and loss_count > win_count:
        return "needs_filter_or_redesign"
    if pnl < 0:
        return "cost_or_tail_risk_problem"
    return "observe"


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
