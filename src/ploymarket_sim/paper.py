from __future__ import annotations

from dataclasses import dataclass
from time import time

from .classifier import classify_market
from .polymarket import Market
from .signals import Signal


@dataclass(frozen=True)
class PaperSignalRow:
    run_timestamp: int
    market_id: str
    market_type: str
    question: str
    yes_price: float | None
    taker_fee_rate: float
    action: str
    confidence: float
    gross_edge: float
    net_edge: float
    reason: str


def build_paper_signal_row(market: Market, signal: Signal, fallback_fee_rate: float, run_timestamp: int | None = None) -> PaperSignalRow:
    return PaperSignalRow(
        run_timestamp=int(run_timestamp if run_timestamp is not None else time()),
        market_id=market.id,
        market_type=classify_market(market).market_type,
        question=market.question,
        yes_price=market.yes_price,
        taker_fee_rate=market.effective_taker_fee_rate(fallback_fee_rate),
        action=signal.action,
        confidence=signal.confidence,
        gross_edge=signal.edge,
        net_edge=signal.net_edge,
        reason=signal.reason,
    )


def summarize_paper_rows(rows: list[PaperSignalRow]) -> dict[str, int]:
    return {
        "markets": len(rows),
        "buy_yes": len([row for row in rows if row.action == "BUY_YES"]),
        "hold": len([row for row in rows if row.action == "HOLD"]),
        "avoid": len([row for row in rows if row.action == "AVOID"]),
    }
