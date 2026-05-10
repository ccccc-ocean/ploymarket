from __future__ import annotations

from dataclasses import dataclass
from time import time

from .classifier import classify_market
from .execution import ExecutionPlan
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
    execution_mode: str
    execution_side: str
    limit_price: float | None
    expected_net_edge: float
    execution_reason: str


def build_paper_signal_row(
    market: Market,
    signal: Signal,
    fallback_fee_rate: float,
    run_timestamp: int | None = None,
    execution_plan: ExecutionPlan | None = None,
) -> PaperSignalRow:
    if execution_plan is None:
        execution_plan = ExecutionPlan("SKIP", "", None, 0.0, signal.net_edge, "未生成执行计划")
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
        execution_mode=execution_plan.mode,
        execution_side=execution_plan.side,
        limit_price=execution_plan.limit_price,
        expected_net_edge=execution_plan.expected_net_edge,
        execution_reason=execution_plan.reason,
    )


def summarize_paper_rows(rows: list[PaperSignalRow]) -> dict[str, int]:
    return {
        "markets": len(rows),
        "buy_yes": len([row for row in rows if row.action == "BUY_YES"]),
        "hold": len([row for row in rows if row.action == "HOLD"]),
        "avoid": len([row for row in rows if row.action == "AVOID"]),
        "taker": len([row for row in rows if row.execution_mode == "TAKER"]),
        "maker": len([row for row in rows if row.execution_mode == "MAKER"]),
        "skip": len([row for row in rows if row.execution_mode == "SKIP"]),
    }
