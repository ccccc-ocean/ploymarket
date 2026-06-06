from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .filter_reason_report import FilterReasonRow, build_filter_reason_report
from .paper_sample_report import PaperSampleRow, build_paper_sample_report


@dataclass(frozen=True)
class StrategyReviewRow:
    market_type: str
    status: str
    recommended_action: str
    reason: str
    taker_count: int
    probe_taker_count: int
    positive_edge_skip_count: int
    max_expected_edge: float
    top_blocker: str


def build_strategy_review(output_dir: str, recent_runs: int = 288) -> list[StrategyReviewRow]:
    samples = build_paper_sample_report(output_dir, recent_runs=recent_runs)
    blockers = _top_blockers_by_type(build_filter_reason_report(output_dir, recent_runs=recent_runs))
    return [_review_sample(row, blockers.get(row.market_type)) for row in samples]


def write_strategy_review_csv(rows: list[StrategyReviewRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "strategy_review.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_type",
                "status",
                "recommended_action",
                "reason",
                "taker_count",
                "probe_taker_count",
                "positive_edge_skip_count",
                "max_expected_edge",
                "top_blocker",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_type,
                    row.status,
                    row.recommended_action,
                    row.reason,
                    row.taker_count,
                    row.probe_taker_count,
                    row.positive_edge_skip_count,
                    row.max_expected_edge,
                    row.top_blocker,
                ]
            )
    return path


def print_strategy_review(rows: list[StrategyReviewRow]) -> None:
    sample_starved = [row for row in rows if row.status == "sample_starved"]
    blocked = [row for row in rows if row.status == "positive_edge_blocked"]
    active = [row for row in rows if row.taker_count > 0]
    print(
        f"strategy_review | active_types={len(active)} | sample_starved={len(sample_starved)} | "
        f"positive_edge_blocked={len(blocked)}"
    )
    for row in rows[:8]:
        print(
            f"strategy_review[{row.market_type}] | status={row.status} | action={row.recommended_action} | "
            f"takers={row.taker_count} | probes={row.probe_taker_count} | "
            f"positive_edge_skips={row.positive_edge_skip_count} | max_edge={row.max_expected_edge:.4f} | "
            f"top_blocker={row.top_blocker}"
        )


def _review_sample(row: PaperSampleRow, blocker: FilterReasonRow | None) -> StrategyReviewRow:
    blocker_label = _blocker_label(blocker)
    if row.market_type in {"company_treasury", "indirect_event"}:
        return StrategyReviewRow(
            market_type=row.market_type,
            status="observe_only",
            recommended_action="keep_observing",
            reason=f"非 BTC 价格结构，暂不进入主模拟盘，避免偏离当前 BTC 策略目标。top_blocker={blocker_label}",
            taker_count=row.taker_count,
            probe_taker_count=row.probe_taker_count,
            positive_edge_skip_count=row.positive_edge_skip_count,
            max_expected_edge=row.max_expected_edge,
            top_blocker=blocker_label,
        )

    if row.row_count >= 200 and row.taker_count == 0 and row.max_expected_edge <= 0:
        return StrategyReviewRow(
            market_type=row.market_type,
            status="no_edge_available",
            recommended_action="do_not_relax_filters_wait_for_market_edge",
            reason=f"样本足够多但近期没有正 expected edge；这不是过滤过严，而是当前盘口/动量不支持入场。top_blocker={blocker_label}",
            taker_count=row.taker_count,
            probe_taker_count=row.probe_taker_count,
            positive_edge_skip_count=row.positive_edge_skip_count,
            max_expected_edge=row.max_expected_edge,
            top_blocker=blocker_label,
        )

    if blocker is not None and blocker.reason_bucket == "edge_too_low" and row.positive_edge_skip_count > 0:
        return StrategyReviewRow(
            market_type=row.market_type,
            status="edge_insufficient",
            recommended_action="maintain_filters_until_edge_improves",
            reason=f"近期主要阻塞是净优势不足，不应为了增加开仓数强行放宽风控。top_blocker={blocker_label}",
            taker_count=row.taker_count,
            probe_taker_count=row.probe_taker_count,
            positive_edge_skip_count=row.positive_edge_skip_count,
            max_expected_edge=row.max_expected_edge,
            top_blocker=blocker_label,
        )

    if row.taker_count == 0 and row.positive_edge_skip_count >= 20:
        return StrategyReviewRow(
            market_type=row.market_type,
            status="positive_edge_blocked",
            recommended_action=_blocked_action(row.market_type),
            reason=f"存在较多正净优势候选但全部被过滤，说明该类型可能不是没有机会，而是入场门槛或专属策略过窄。top_blocker={blocker_label}",
            taker_count=row.taker_count,
            probe_taker_count=row.probe_taker_count,
            positive_edge_skip_count=row.positive_edge_skip_count,
            max_expected_edge=row.max_expected_edge,
            top_blocker=blocker_label,
        )

    if row.row_count >= 200 and row.taker_count == 0:
        return StrategyReviewRow(
            market_type=row.market_type,
            status="sample_starved",
            recommended_action="review_filters_before_relaxing",
            reason=f"样本足够多但没有成交，应优先复查过滤原因分布，而不是直接放宽止损或硬开仓。top_blocker={blocker_label}",
            taker_count=row.taker_count,
            probe_taker_count=row.probe_taker_count,
            positive_edge_skip_count=row.positive_edge_skip_count,
            max_expected_edge=row.max_expected_edge,
            top_blocker=blocker_label,
        )

    if row.probe_taker_count > 0:
        return StrategyReviewRow(
            market_type=row.market_type,
            status="probe_active",
            recommended_action="monitor_probe_pnl",
            reason="探索仓已产生样本，下一步看真实 paper_account_pnl 和止损频率，不因单个 strike 盈亏做刻舟求剑调整。",
            taker_count=row.taker_count,
            probe_taker_count=row.probe_taker_count,
            positive_edge_skip_count=row.positive_edge_skip_count,
            max_expected_edge=row.max_expected_edge,
            top_blocker=blocker_label,
        )

    return StrategyReviewRow(
        market_type=row.market_type,
        status="normal",
        recommended_action="maintain",
        reason="当前没有明显样本饥饿或正 edge 被大量过滤的迹象。",
        taker_count=row.taker_count,
        probe_taker_count=row.probe_taker_count,
        positive_edge_skip_count=row.positive_edge_skip_count,
        max_expected_edge=row.max_expected_edge,
        top_blocker=blocker_label,
    )


def _blocked_action(market_type: str) -> str:
    if market_type == "touch_below":
        return "design_touch_below_probe_with_strict_price_and_btc_confirmation"
    if market_type == "touch_above":
        return "keep_observing_until_edge_is_persistent"
    if market_type == "range_bucket":
        return "loosen_range_probe_in_small_size"
    if market_type == "above_below_expiry":
        return "allow_small_size_certainty_no_or_yes_probe"
    return "review_type_specific_filters"


def _top_blockers_by_type(rows: list[FilterReasonRow]) -> dict[str, FilterReasonRow]:
    blockers: dict[str, FilterReasonRow] = {}
    for row in rows:
        current = blockers.get(row.market_type)
        if current is None or (row.positive_edge_count, row.max_expected_edge, row.row_count) > (
            current.positive_edge_count,
            current.max_expected_edge,
            current.row_count,
        ):
            blockers[row.market_type] = row
    return blockers


def _blocker_label(row: FilterReasonRow | None) -> str:
    if row is None:
        return "none"
    return f"{row.reason_bucket}:{row.positive_edge_count}/{row.row_count}"
