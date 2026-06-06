from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .classifier import classify_market
from .polymarket import Market
from .probe_performance_report import probe_family_from_reason
from .storage import PaperPositionState


@dataclass(frozen=True)
class OpenPositionReportRow:
    market_id: str
    market_type: str
    question: str
    side: str
    entry_price: float
    current_price: float | None
    current_price_source: str
    shares: float
    notional: float
    realized_pnl: float
    unrealized_pnl: float | None
    estimated_total_pnl: float | None
    pnl_pct: float | None
    opened_at: int
    age_seconds: int
    end_date: str
    seconds_to_expiry: int | None
    expiry_status: str
    probe_family: str
    partial_take_profit_count: int


def build_open_position_report(
    output_dir: str,
    markets: list[Market],
    positions: list[PaperPositionState],
    now_timestamp: int,
    live_side_prices: dict[str, float | None] | None = None,
) -> list[OpenPositionReportRow]:
    market_by_id = {market.id: market for market in markets}
    probe_families = _load_probe_entry_families(output_dir)
    live_side_prices = live_side_prices or {}
    rows = []
    for position in sorted(positions, key=lambda item: item.opened_at):
        market = market_by_id.get(position.market_id)
        market_type = classify_market(market).market_type if market is not None else "unknown"
        question = market.question if market is not None else ""
        stored_price = _stored_side_price(market, position.side) if market is not None else None
        live_price = live_side_prices.get(position.market_id)
        if live_price is not None:
            current_price = live_price
            current_price_source = "live_bid"
        elif stored_price is not None:
            current_price = stored_price
            current_price_source = "stored_market_price"
        else:
            current_price = None
            current_price_source = "unavailable"
        unrealized_pnl = None if current_price is None else (current_price - position.entry_price) * position.shares
        estimated_total_pnl = None if unrealized_pnl is None else position.realized_pnl + unrealized_pnl
        pnl_pct = None if current_price is None or position.entry_price <= 0 else current_price / position.entry_price - 1.0
        end_date = market.end_date if market is not None and market.end_date else ""
        expiry_timestamp = _parse_end_date_timestamp(end_date)
        seconds_to_expiry = None if expiry_timestamp is None else expiry_timestamp - now_timestamp
        rows.append(
            OpenPositionReportRow(
                market_id=position.market_id,
                market_type=market_type,
                question=question,
                side=position.side,
                entry_price=position.entry_price,
                current_price=current_price,
                current_price_source=current_price_source,
                shares=position.shares,
                notional=position.notional,
                realized_pnl=position.realized_pnl,
                unrealized_pnl=unrealized_pnl,
                estimated_total_pnl=estimated_total_pnl,
                pnl_pct=pnl_pct,
                opened_at=position.opened_at,
                age_seconds=max(0, now_timestamp - position.opened_at),
                end_date=end_date,
                seconds_to_expiry=seconds_to_expiry,
                expiry_status=_expiry_status(seconds_to_expiry, end_date),
                probe_family=probe_families.get((position.market_id, position.opened_at), ""),
                partial_take_profit_count=position.partial_take_profit_count,
            )
        )
    return rows


def write_open_position_report_csv(rows: list[OpenPositionReportRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "open_position_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_id",
                "market_type",
                "question",
                "side",
                "entry_price",
                "current_price",
                "current_price_source",
                "shares",
                "notional",
                "realized_pnl",
                "unrealized_pnl",
                "estimated_total_pnl",
                "pnl_pct",
                "opened_at",
                "age_seconds",
                "end_date",
                "seconds_to_expiry",
                "expiry_status",
                "probe_family",
                "partial_take_profit_count",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_id,
                    row.market_type,
                    row.question,
                    row.side,
                    row.entry_price,
                    _optional_float(row.current_price),
                    row.current_price_source,
                    row.shares,
                    row.notional,
                    row.realized_pnl,
                    _optional_float(row.unrealized_pnl),
                    _optional_float(row.estimated_total_pnl),
                    _optional_float(row.pnl_pct),
                    row.opened_at,
                    row.age_seconds,
                    row.end_date,
                    "" if row.seconds_to_expiry is None else row.seconds_to_expiry,
                    row.expiry_status,
                    row.probe_family,
                    row.partial_take_profit_count,
                ]
            )
    return path


def print_open_position_report(rows: list[OpenPositionReportRow]) -> None:
    total_notional = sum(row.notional for row in rows)
    estimated_pnl = sum(row.estimated_total_pnl or 0.0 for row in rows)
    expired = len([row for row in rows if row.expiry_status == "expired_pending_settlement"])
    probes = len([row for row in rows if row.probe_family])
    print(
        f"open_position_report | open={len(rows)} | probes={probes} | "
        f"notional={total_notional:.2f} | estimated_total_pnl={estimated_pnl:.4f} | expired_pending={expired}"
    )
    for row in rows[:20]:
        pnl = "na" if row.estimated_total_pnl is None else f"{row.estimated_total_pnl:.4f}"
        price = "na" if row.current_price is None else f"{row.current_price:.3f}"
        print(
            f"open_position[{row.market_type}/{row.side}] | market={row.market_id} | price={price} "
            f"source={row.current_price_source} | pnl={pnl} | expiry={row.expiry_status} | "
            f"probe={row.probe_family or 'no'} | question={row.question}"
        )


def _stored_side_price(market: Market, side: str) -> float | None:
    return market.yes_price if side == "YES" else market.no_price


def _expiry_status(seconds_to_expiry: int | None, end_date: str) -> str:
    if not end_date:
        return "no_end_date"
    if seconds_to_expiry is None:
        return "unknown_end_date"
    if seconds_to_expiry < 0:
        return "expired_pending_settlement"
    return "pre_expiry"


def _parse_end_date_timestamp(end_date: str) -> int | None:
    if not end_date:
        return None
    try:
        value = end_date.replace("Z", "+00:00")
        return int(datetime.fromisoformat(value).astimezone(timezone.utc).timestamp())
    except ValueError:
        return None


def _load_probe_entry_families(output_dir: str) -> dict[tuple[str, int], str]:
    families: dict[tuple[str, int], str] = {}
    for path in sorted(Path(output_dir).glob("paper_run_*.csv")):
        with path.open("r", newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if row.get("execution_mode") != "TAKER":
                    continue
                reason = row.get("reason", "")
                if "探索仓" not in reason and "挑战仓" not in reason:
                    continue
                try:
                    opened_at = int(float(row.get("run_timestamp") or 0))
                except ValueError:
                    continue
                families[(row.get("market_id", ""), opened_at)] = probe_family_from_reason(reason)
    return families


def _optional_float(value: float | None) -> str:
    return "" if value is None else f"{value:.10g}"
