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
    partial_fill_cancels: int
    fail_safe_scenarios: int


@dataclass(frozen=True)
class ShadowOrderEvent:
    run_timestamp: int
    market_id: str
    side: str
    scenario: str
    event_sequence: int
    status: str
    requested_notional: float
    filled_notional: float
    reserved_exposure: float
    control_action: str
    reason: str


@dataclass(frozen=True)
class ExecutionStressHistory:
    runs: int
    candidates: int
    robust_candidates: int
    latency_blocked_candidates: int
    partial_fill_cancels: int
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
        market_rows = [row for row in rows if row.market_id == market_id and _is_price_stress(row)]
        if market_rows and all(row.outcome == "PASS" for row in market_rows):
            robust_candidates += 1
    return ExecutionStressSummary(
        candidates=len(candidate_ids),
        scenarios=len(rows),
        robust_candidates=robust_candidates,
        market_stress_blocks=len([row for row in rows if _is_price_stress(row) and row.outcome == "BLOCK"]),
        partial_fill_cancels=len(
            [row for row in rows if row.scenario.startswith("partial_fill_") and row.control_action == "CANCEL_REMAINDER"]
        ),
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


def build_shadow_order_events(rows: list[ExecutionStressRow]) -> list[ShadowOrderEvent]:
    events: list[ShadowOrderEvent] = []
    for row in rows:
        requested = row.filled_notional + row.unfilled_notional
        if row.scenario.startswith("latency_adverse_") or row.scenario == "baseline":
            if row.outcome == "PASS":
                events.extend(
                    [
                        _event(row, 1, "SUBMITTED", 0.0, requested),
                        _event(row, 2, "FILLED", requested, requested),
                    ]
                )
            else:
                events.append(_event(row, 1, "REJECTED_PRE_SUBMIT", 0.0, 0.0))
        elif row.scenario.startswith("partial_fill_"):
            events.extend(
                [
                    _event(row, 1, "SUBMITTED", 0.0, requested),
                    _event(row, 2, "PARTIALLY_FILLED", row.filled_notional, row.filled_notional),
                    _event(row, 3, "CANCELED_REMAINDER", row.filled_notional, row.filled_notional),
                ]
            )
        elif row.scenario == "cancel_failure_after_partial_fill":
            events.extend(
                [
                    _event(row, 1, "SUBMITTED", 0.0, requested),
                    _event(row, 2, "PARTIALLY_FILLED", row.filled_notional, requested),
                    _event(row, 3, "CANCEL_PENDING", row.filled_notional, requested),
                ]
            )
        else:
            events.append(_event(row, 1, "REJECTED", 0.0, 0.0))
    return events


def write_shadow_order_events_csv(events: list[ShadowOrderEvent], output_dir: str, run_timestamp: int) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"shadow_order_events_{run_timestamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "run_timestamp",
                "market_id",
                "side",
                "scenario",
                "event_sequence",
                "status",
                "requested_notional",
                "filled_notional",
                "reserved_exposure",
                "control_action",
                "reason",
            ]
        )
        for event in events:
            writer.writerow(
                [
                    event.run_timestamp,
                    event.market_id,
                    event.side,
                    event.scenario,
                    event.event_sequence,
                    event.status,
                    event.requested_notional,
                    event.filled_notional,
                    event.reserved_exposure,
                    event.control_action,
                    event.reason,
                ]
            )
    return path


def load_execution_stress_history(output_dir: str) -> list[ExecutionStressRow]:
    rows: list[ExecutionStressRow] = []
    for path in sorted(Path(output_dir).glob("execution_stress_[0-9]*.csv")):
        with path.open(newline="", encoding="utf-8") as file:
            for raw in csv.DictReader(file):
                rows.append(
                    ExecutionStressRow(
                        run_timestamp=int(raw["run_timestamp"]),
                        market_id=raw["market_id"],
                        question=raw["question"],
                        side=raw["side"],
                        scenario=raw["scenario"],
                        reference_price=float(raw["reference_price"]),
                        stressed_price=_optional_float(raw["stressed_price"]),
                        expected_net_edge=float(raw["expected_net_edge"]),
                        stressed_net_edge=_optional_float(raw["stressed_net_edge"]),
                        fill_fraction=float(raw["fill_fraction"]),
                        filled_notional=float(raw["filled_notional"]),
                        unfilled_notional=float(raw["unfilled_notional"]),
                        outcome=raw["outcome"],
                        control_action=raw["control_action"],
                        reason=raw["reason"],
                    )
                )
    return rows


def summarize_execution_stress_history(
    rows: list[ExecutionStressRow],
    observed_run_count: int | None = None,
) -> ExecutionStressHistory:
    run_ids = {row.run_timestamp for row in rows}
    candidate_ids = {(row.run_timestamp, row.market_id) for row in rows}
    robust = 0
    latency_blocked = 0
    for candidate_id in candidate_ids:
        price_rows = [
            row for row in rows if (row.run_timestamp, row.market_id) == candidate_id and _is_price_stress(row)
        ]
        if price_rows and all(row.outcome == "PASS" for row in price_rows):
            robust += 1
        elif price_rows:
            latency_blocked += 1
    return ExecutionStressHistory(
        runs=max(len(run_ids), observed_run_count or 0),
        candidates=len(candidate_ids),
        robust_candidates=robust,
        latency_blocked_candidates=latency_blocked,
        partial_fill_cancels=len(
            [row for row in rows if row.scenario.startswith("partial_fill_") and row.control_action == "CANCEL_REMAINDER"]
        ),
        fail_safe_scenarios=len([row for row in rows if row.outcome == "FAIL_SAFE"]),
    )


def write_execution_stress_report_csv(summary: ExecutionStressHistory, output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "execution_stress_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "runs",
                "candidates",
                "robust_candidates",
                "latency_blocked_candidates",
                "partial_fill_cancels",
                "fail_safe_scenarios",
            ]
        )
        writer.writerow(
            [
                summary.runs,
                summary.candidates,
                summary.robust_candidates,
                summary.latency_blocked_candidates,
                summary.partial_fill_cancels,
                summary.fail_safe_scenarios,
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
    elif fill_fraction < 1.0:
        action = "CANCEL_REMAINDER"
        reason = "允许管理已成交仓位，并撤销未成交余量"
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


def _event(
    row: ExecutionStressRow,
    sequence: int,
    status: str,
    filled_notional: float,
    reserved_exposure: float,
) -> ShadowOrderEvent:
    return ShadowOrderEvent(
        run_timestamp=row.run_timestamp,
        market_id=row.market_id,
        side=row.side,
        scenario=row.scenario,
        event_sequence=sequence,
        status=status,
        requested_notional=row.filled_notional + row.unfilled_notional,
        filled_notional=filled_notional,
        reserved_exposure=reserved_exposure,
        control_action=row.control_action,
        reason=row.reason,
    )


def _is_price_stress(row: ExecutionStressRow) -> bool:
    return row.scenario == "baseline" or row.scenario.startswith("latency_adverse_")


def _optional_float(value: str) -> float | None:
    return float(value) if value else None
