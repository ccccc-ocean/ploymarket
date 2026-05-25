from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .config import ExecutionStressConfig
from .paper import PaperSignalRow


@dataclass(frozen=True)
class ExecutionStressRow:
    run_timestamp: int
    market_id: str
    question: str
    side: str
    scenario: str
    reference_price: float
    stressed_price: float | None
    expected_net_edge: float
    stressed_net_edge: float | None
    fill_fraction: float
    filled_notional: float
    unfilled_notional: float
    outcome: str
    control_action: str
    reason: str


@dataclass(frozen=True)
class ExecutionStressSummary:
    candidates: int
    scenarios: int
    robust_candidates: int
    market_stress_blocks: int
    fail_safe_scenarios: int


def build_execution_stress_rows(
    paper_rows: list[PaperSignalRow],
    config: ExecutionStressConfig,
    trade_size_usdc: float,
) -> list[ExecutionStressRow]:
    rows: list[ExecutionStressRow] = []
    candidates = [
        row
        for row in paper_rows
        if row.execution_mode == "TAKER" and row.limit_price is not None
    ]
    for candidate in candidates:
        rows.append(_market_stress_row(candidate, "baseline", 0.0, 1.0, config, trade_size_usdc))
        for adverse_move in config.adverse_price_moves:
            label = f"latency_adverse_{adverse_move:.4f}"
            rows.append(_market_stress_row(candidate, label, adverse_move, 1.0, config, trade_size_usdc))
        for fill_fraction in config.partial_fill_fractions:
            label = f"partial_fill_{fill_fraction:.2f}"
            rows.append(_market_stress_row(candidate, label, 0.0, fill_fraction, config, trade_size_usdc))
        rows.extend(_operational_failure_rows(candidate, config, trade_size_usdc))
    return rows


def summarize_execution_stress(rows: list[ExecutionStressRow]) -> ExecutionStressSummary:
    candidate_ids = {row.market_id for row in rows}
    robust_candidates = 0
    for market_id in candidate_ids:
        market_rows = [row for row in rows if row.market_id == market_id and row.outcome != "FAIL_SAFE"]
        if market_rows and all(row.outcome == "PASS" for row in market_rows):
            robust_candidates += 1
    return ExecutionStressSummary(
        candidates=len(candidate_ids),
        scenarios=len(rows),
        robust_candidates=robust_candidates,
        market_stress_blocks=len([row for row in rows if row.outcome == "BLOCK"]),
        fail_safe_scenarios=len([row for row in rows if row.outcome == "FAIL_SAFE"]),
    )


def write_execution_stress_csv(rows: list[ExecutionStressRow], output_dir: str, run_timestamp: int) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"execution_stress_{run_timestamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "run_timestamp",
                "market_id",
                "question",
                "side",
                "scenario",
                "reference_price",
                "stressed_price",
                "expected_net_edge",
                "stressed_net_edge",
                "fill_fraction",
                "filled_notional",
                "unfilled_notional",
                "outcome",
                "control_action",
                "reason",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.run_timestamp,
                    row.market_id,
                    row.question,
                    row.side,
                    row.scenario,
                    row.reference_price,
                    row.stressed_price,
                    row.expected_net_edge,
                    row.stressed_net_edge,
                    row.fill_fraction,
                    row.filled_notional,
                    row.unfilled_notional,
                    row.outcome,
                    row.control_action,
                    row.reason,
                ]
            )
    return path


def _market_stress_row(
    candidate: PaperSignalRow,
    scenario: str,
    adverse_price_move: float,
    fill_fraction: float,
    config: ExecutionStressConfig,
    trade_size_usdc: float,
) -> ExecutionStressRow:
    reference_price = float(candidate.limit_price or 0.0)
    stressed_price = min(0.999, reference_price + adverse_price_move)
    stressed_edge = candidate.expected_net_edge - (stressed_price - reference_price)
    unfilled_fraction = 1.0 - fill_fraction
    outcome = "PASS"
    action = "ALLOW_SHADOW_FILL"
    reason = "候选在执行摩擦下仍保留最低净 edge"
    if stressed_edge < config.min_surviving_net_edge:
        outcome = "BLOCK"
        action = "REJECT_NEW_ORDER"
        reason = "价格恶化后净 edge 不足，不追价成交"
    elif unfilled_fraction > config.max_unfilled_fraction:
        outcome = "BLOCK"
        action = "CANCEL_REMAINDER"
        reason = "未成交残量超过阈值，撤销剩余订单并仅管理已成交仓位"
    return ExecutionStressRow(
        run_timestamp=candidate.run_timestamp,
        market_id=candidate.market_id,
        question=candidate.question,
        side=candidate.execution_side,
        scenario=scenario,
        reference_price=reference_price,
        stressed_price=stressed_price,
        expected_net_edge=candidate.expected_net_edge,
        stressed_net_edge=stressed_edge,
        fill_fraction=fill_fraction,
        filled_notional=trade_size_usdc * fill_fraction,
        unfilled_notional=trade_size_usdc * unfilled_fraction,
        outcome=outcome,
        control_action=action,
        reason=reason,
    )


def _operational_failure_rows(
    candidate: PaperSignalRow,
    config: ExecutionStressConfig,
    trade_size_usdc: float,
) -> list[ExecutionStressRow]:
    pause_reason = f"暂停新单 {config.operational_failure_pause_seconds} 秒，连续 {config.consecutive_failure_circuit_breaker} 次触发熔断"
    return [
        _fail_safe_row(candidate, "signature_or_auth_failure", trade_size_usdc, "PAUSE_NEW_ORDERS", pause_reason),
        _fail_safe_row(candidate, "balance_or_allowance_failure", trade_size_usdc, "PAUSE_NEW_ORDERS", pause_reason),
        _fail_safe_row(
            candidate,
            "cancel_failure_after_partial_fill",
            trade_size_usdc,
            "FREEZE_MARKET_AND_RECONCILE",
            "撤单未确认时按最坏持仓占用敞口，禁止该市场继续加仓",
            fill_fraction=0.5,
        ),
    ]


def _fail_safe_row(
    candidate: PaperSignalRow,
    scenario: str,
    trade_size_usdc: float,
    action: str,
    reason: str,
    fill_fraction: float = 0.0,
) -> ExecutionStressRow:
    return ExecutionStressRow(
        run_timestamp=candidate.run_timestamp,
        market_id=candidate.market_id,
        question=candidate.question,
        side=candidate.execution_side,
        scenario=scenario,
        reference_price=float(candidate.limit_price or 0.0),
        stressed_price=None,
        expected_net_edge=candidate.expected_net_edge,
        stressed_net_edge=None,
        fill_fraction=fill_fraction,
        filled_notional=trade_size_usdc * fill_fraction,
        unfilled_notional=trade_size_usdc * (1.0 - fill_fraction),
        outcome="FAIL_SAFE",
        control_action=action,
        reason=reason,
    )
