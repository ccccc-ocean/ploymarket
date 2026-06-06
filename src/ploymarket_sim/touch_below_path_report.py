from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .market_rules import extract_usd_strike, latest_btc_candle_at_or_before


@dataclass(frozen=True)
class TouchBelowPathRow:
    market_id: str
    question: str
    row_count: int
    positive_edge_count: int
    max_expected_edge: float
    latest_yes_price: float
    latest_no_price: float
    btc_price: float
    strike: float
    distance_pct: float
    return_15m: float | None
    return_1h: float | None
    path_state: str


def build_touch_below_path_report(output_dir: str, btc_candles, recent_runs: int = 288) -> list[TouchBelowPathRow]:
    paths = sorted(Path(output_dir).glob("paper_run_*.csv"))[-max(1, recent_runs) :]
    grouped: dict[str, list[dict[str, str]]] = {}
    for path in paths:
        for row in _read_rows(path):
            if row.get("market_type") != "touch_below":
                continue
            grouped.setdefault(row.get("market_id", ""), []).append(row)

    rows = []
    for market_id, items in grouped.items():
        latest = max(items, key=lambda row: _int(row.get("run_timestamp")), default={})
        question = latest.get("question", "")
        timestamp = _int(latest.get("run_timestamp"))
        candle = latest_btc_candle_at_or_before(btc_candles, timestamp)
        strike = extract_usd_strike(question)
        yes_price = _float(latest.get("yes_price"))
        if candle is None or candle.close <= 0 or strike is None:
            distance_pct = 0.0
            btc_price = 0.0
            return_15m = None
            return_1h = None
            path_state = "missing_btc_or_strike"
        else:
            btc_price = candle.close
            distance_pct = (btc_price - strike) / btc_price
            return_15m = _return_since(btc_candles, timestamp, 15 * 60, btc_price)
            return_1h = _return_since(btc_candles, timestamp, 60 * 60, btc_price)
            path_state = _path_state(yes_price, distance_pct, return_15m, return_1h)
        positive_edges = [_float(row.get("expected_net_edge")) for row in items if _float(row.get("expected_net_edge")) > 0]
        rows.append(
            TouchBelowPathRow(
                market_id=market_id,
                question=question,
                row_count=len(items),
                positive_edge_count=len(positive_edges),
                max_expected_edge=max(positive_edges, default=0.0),
                latest_yes_price=yes_price,
                latest_no_price=max(0.0, 1.0 - yes_price),
                btc_price=btc_price,
                strike=strike or 0.0,
                distance_pct=distance_pct,
                return_15m=return_15m,
                return_1h=return_1h,
                path_state=path_state,
            )
        )
    return sorted(rows, key=lambda row: (row.positive_edge_count, row.max_expected_edge), reverse=True)


def write_touch_below_path_report_csv(rows: list[TouchBelowPathRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "touch_below_path_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_id",
                "question",
                "row_count",
                "positive_edge_count",
                "max_expected_edge",
                "latest_yes_price",
                "latest_no_price",
                "btc_price",
                "strike",
                "distance_pct",
                "return_15m",
                "return_1h",
                "path_state",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_id,
                    row.question,
                    row.row_count,
                    row.positive_edge_count,
                    row.max_expected_edge,
                    row.latest_yes_price,
                    row.latest_no_price,
                    row.btc_price,
                    row.strike,
                    row.distance_pct,
                    "" if row.return_15m is None else row.return_15m,
                    "" if row.return_1h is None else row.return_1h,
                    row.path_state,
                ]
            )
    return path


def print_touch_below_path_report(rows: list[TouchBelowPathRow]) -> None:
    state_counts: dict[str, int] = {}
    for row in rows:
        state_counts[row.path_state] = state_counts.get(row.path_state, 0) + 1
    state_summary = ";".join(f"{state}:{count}" for state, count in sorted(state_counts.items()))
    print(f"touch_below_path_report | markets={len(rows)} | states={state_summary or 'none'}")
    for row in rows[:12]:
        print(
            f"touch_below_path[{row.path_state}] | market={row.market_id} | pos_edge={row.positive_edge_count} | "
            f"max_edge={row.max_expected_edge:.4f} | yes={row.latest_yes_price:.3f} | no={row.latest_no_price:.3f} | "
            f"distance={row.distance_pct:.2%} | 15m={_fmt_pct(row.return_15m)} | 1h={_fmt_pct(row.return_1h)}"
        )


def _path_state(yes_price: float, distance_pct: float, return_15m: float | None, return_1h: float | None) -> str:
    if yes_price >= 0.98:
        return "yes_near_resolved_or_triggered"
    if distance_pct <= 0:
        return "btc_at_or_below_target"
    if distance_pct < 0.055:
        return "too_close_to_target_for_no"
    if (return_15m is not None and return_15m <= -0.0025) or (return_1h is not None and return_1h <= -0.006):
        return "falling_toward_target"
    if 0.25 <= 1.0 - yes_price <= 0.72:
        return "distance_no_probe_candidate"
    return "observe_only"


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _return_since(candles, timestamp: int, lookback_seconds: int, current_close: float) -> float | None:
    previous = latest_btc_candle_at_or_before(candles, timestamp - lookback_seconds)
    if previous is None or previous.close == 0:
        return None
    return (current_close - previous.close) / previous.close


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0


def _int(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0
