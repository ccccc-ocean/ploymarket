from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .storage import PaperPositionState


@dataclass(frozen=True)
class ProbePerformanceRow:
    probe_family: str
    market_type: str
    opened_count: int
    closed_count: int
    open_count: int
    realized_pnl: float
    win_count: int
    loss_count: int
    win_rate: float
    average_realized_pnl: float
    latest_opened_at: int


def build_probe_performance_report(output_dir: str, closed_positions: list[PaperPositionState], open_market_ids: set[str]) -> list[ProbePerformanceRow]:
    probe_entries = _load_probe_entries(output_dir)
    closed_by_key = {(position.market_id, position.opened_at): position for position in closed_positions}
    grouped: dict[tuple[str, str], list[tuple[dict[str, str], PaperPositionState | None, bool]]] = {}
    for entry in probe_entries:
        market_id = entry.get("market_id", "")
        opened_at = int(float(entry.get("run_timestamp") or 0))
        family = _probe_family(entry.get("reason", ""))
        market_type = entry.get("market_type", "unknown")
        closed = closed_by_key.get((market_id, opened_at))
        is_open = closed is None and market_id in open_market_ids
        grouped.setdefault((family, market_type), []).append((entry, closed, is_open))

    rows = []
    for (family, market_type), items in grouped.items():
        closed_items = [closed for _entry, closed, _is_open in items if closed is not None]
        open_count = len([1 for _entry, closed, is_open in items if closed is None and is_open])
        realized_pnl = sum(position.realized_pnl for position in closed_items)
        win_count = len([position for position in closed_items if position.realized_pnl > 0])
        loss_count = len([position for position in closed_items if position.realized_pnl < 0])
        closed_count = len(closed_items)
        rows.append(
            ProbePerformanceRow(
                probe_family=family,
                market_type=market_type,
                opened_count=len(items),
                closed_count=closed_count,
                open_count=open_count,
                realized_pnl=realized_pnl,
                win_count=win_count,
                loss_count=loss_count,
                win_rate=win_count / closed_count if closed_count else 0.0,
                average_realized_pnl=realized_pnl / closed_count if closed_count else 0.0,
                latest_opened_at=max(int(float(entry.get("run_timestamp") or 0)) for entry, _closed, _is_open in items),
            )
        )
    return sorted(rows, key=lambda row: (row.realized_pnl, row.closed_count, row.opened_count), reverse=True)


def write_probe_performance_report_csv(rows: list[ProbePerformanceRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "probe_performance_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "probe_family",
                "market_type",
                "opened_count",
                "closed_count",
                "open_count",
                "realized_pnl",
                "win_count",
                "loss_count",
                "win_rate",
                "average_realized_pnl",
                "latest_opened_at",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.probe_family,
                    row.market_type,
                    row.opened_count,
                    row.closed_count,
                    row.open_count,
                    row.realized_pnl,
                    row.win_count,
                    row.loss_count,
                    row.win_rate,
                    row.average_realized_pnl,
                    row.latest_opened_at,
                ]
            )
    return path


def print_probe_performance_report(rows: list[ProbePerformanceRow]) -> None:
    opened = sum(row.opened_count for row in rows)
    closed = sum(row.closed_count for row in rows)
    realized_pnl = sum(row.realized_pnl for row in rows)
    print(f"probe_performance_report | families={len(rows)} | opened={opened} | closed={closed} | realized_pnl={realized_pnl:.4f}")
    for row in rows[:8]:
        print(
            f"probe_performance[{row.market_type}/{row.probe_family}] | opened={row.opened_count} | "
            f"closed={row.closed_count} | open={row.open_count} | pnl={row.realized_pnl:.4f} | "
            f"win_rate={row.win_rate:.2%}"
        )


def _load_probe_entries(output_dir: str) -> list[dict[str, str]]:
    entries = []
    for path in sorted(Path(output_dir).glob("paper_run_*.csv")):
        with path.open("r", newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if row.get("execution_mode") != "TAKER":
                    continue
                reason = row.get("reason", "")
                if "探索仓" in reason or "挑战仓" in reason:
                    entries.append(row)
    return entries


def _probe_family(reason: str) -> str:
    return probe_family_from_reason(reason)


def probe_family_from_reason(reason: str) -> str:
    if "过滤器挑战仓" in reason:
        return "regime_filter_challenge"
    if "超高确定性 above_below_expiry/NO v1" in reason:
        return "ultra_certainty_above_below_no"
    if "crossed-above 回落 above_below_expiry/NO v1" in reason:
        return "crossed_above_reversal_no"
    if "高确定性 above_below_expiry/NO" in reason:
        return "certainty_above_below_no"
    if "超高确定性 above_below_expiry/YES v1" in reason:
        return "ultra_certainty_above_below_yes"
    if "高确定性 above_below_expiry/YES v1" in reason:
        return "certainty_above_below_yes"
    if "样本恢复 above_below_expiry/NO v1" in reason:
        return "recovery_above_below_no"
    if "高价正edge above_below_expiry/NO" in reason:
        return "expensive_edge_above_below_no"
    if "near-strike 安全带 above_below_expiry/NO" in reason:
        return "near_strike_above_below_no"
    if "区间中心 range_bucket/YES v1" in reason:
        return "range_bucket_center_yes"
    if "range_bucket/YES" in reason:
        return "range_bucket_yes"
    if "折扣 touch_below/YES v2" in reason:
        return "touch_below_discount_yes"
    if "高确定性 touch_below/NO v2" in reason:
        return "touch_below_certainty_no"
    if "距离安全 touch_below/NO v1" in reason:
        return "touch_below_distance_no"
    if "touch_below/NO v1" in reason:
        return "touch_below_no"
    if "touch_below/YES momentum v1" in reason:
        return "touch_below_momentum_yes"
    if "touch_below/YES" in reason:
        return "touch_below_yes"
    if "above_below_expiry/YES" in reason:
        return "above_below_yes"
    if "above_below_expiry/NO" in reason:
        return "above_below_no"
    return "other_probe"
