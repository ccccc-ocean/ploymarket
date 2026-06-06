from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .probe_performance_report import ProbePerformanceRow
from .strategy_review import StrategyReviewRow


@dataclass(frozen=True)
class AutotuneContext:
    open_positions: int
    probe_slots: int
    open_exposure_usdc: float
    probe_max_exposure_usdc: float
    disabled_probe_families: list[str]
    zero_taker_streak: int
    probe_zero_run_threshold: int = 1


@dataclass(frozen=True)
class StrategyAutotuneRow:
    priority: int
    scope: str
    action: str
    status: str
    reason: str
    evidence: str


def build_strategy_autotune_report(
    strategy_rows: list[StrategyReviewRow],
    probe_rows: list[ProbePerformanceRow],
    context: AutotuneContext,
) -> list[StrategyAutotuneRow]:
    rows: list[StrategyAutotuneRow] = []
    rows.extend(_disabled_probe_actions(context.disabled_probe_families))
    rows.extend(_probe_performance_actions(probe_rows))
    rows.extend(_pending_probe_market_actions(strategy_rows, probe_rows))
    rows.extend(_strategy_review_actions(strategy_rows, context))
    rows.append(_slot_action(context))
    return sorted(rows, key=lambda row: row.priority)


def write_strategy_autotune_report_csv(rows: list[StrategyAutotuneRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "strategy_autotune_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["priority", "scope", "action", "status", "reason", "evidence"])
        for row in rows:
            writer.writerow([row.priority, row.scope, row.action, row.status, row.reason, row.evidence])
    return path


def print_strategy_autotune_report(rows: list[StrategyAutotuneRow]) -> None:
    urgent = len([row for row in rows if row.priority <= 20])
    print(f"strategy_autotune_report | rows={len(rows)} | urgent={urgent}")
    for row in rows[:10]:
        print(
            f"strategy_autotune[{row.scope}] | priority={row.priority} | action={row.action} | "
            f"status={row.status} | evidence={row.evidence}"
        )


def _disabled_probe_actions(disabled_families: list[str]) -> list[StrategyAutotuneRow]:
    return [
        StrategyAutotuneRow(
            priority=10,
            scope=f"probe_family/{family}",
            action=_disabled_probe_redesign_action(family),
            status="disabled_after_losses",
            reason=_disabled_probe_redesign_reason(family),
            evidence=f"disabled_family={family}",
        )
        for family in disabled_families
    ]


def _disabled_probe_redesign_action(family: str) -> str:
    actions = {
        "regime_filter_challenge": "redesign_require_strike_retreat_before_regime_challenge",
        "expensive_edge_above_below_no": "redesign_high_price_no_with_reversal_risk_cap",
        "range_bucket_yes": "redesign_range_bucket_with_boundary_and_time_filter",
        "certainty_above_below_yes": "redesign_certainty_yes_with_stronger_retreat_guard",
        "ultra_certainty_above_below_no": "redesign_ultra_certainty_no_with_min_profit_guard",
        "ultra_certainty_above_below_yes": "redesign_ultra_certainty_yes_with_min_profit_guard",
        "recovery_above_below_no": "redesign_recovery_no_with_wider_strike_buffer",
        "touch_below_no": "redesign_touch_below_no_with_larger_target_buffer",
        "touch_below_yes": "redesign_touch_below_yes_with_downward_confirmation",
        "touch_below_discount_yes": "keep_touch_below_discount_yes_disabled_until_path_edge_model",
        "touch_below_momentum_yes": "keep_touch_below_momentum_yes_disabled_until_path_edge_model",
        "above_below_yes": "redesign_above_below_yes_with_breakout_confirmation",
        "range_bucket_center_yes": "monitor_range_center_probe_before_promotion",
    }
    return actions.get(family, "keep_disabled_until_new_design")


def _disabled_probe_redesign_reason(family: str) -> str:
    reasons = {
        "regime_filter_challenge": (
            "该探索家族亏损说明“被 regime/近 strike 风控拦截后仍挑战”质量不稳定；重启前必须要求 BTC 明确远离 strike，"
            "并保留连续亏损暂停，不能为了增加开仓数直接恢复。"
        ),
        "expensive_edge_above_below_no": (
            "高价 BUY_NO 虽有表面 edge，但反抽时盈亏比会迅速恶化；重启前要加入更强的反抽风险上限和更远 strike 安全带。"
        ),
        "range_bucket_yes": (
            "range_bucket/YES 对边界距离和到期时间敏感；重启前要按区间宽度、边界距离和波动状态重新设计，而不是平移旧策略。"
        ),
        "certainty_above_below_yes": (
            "高确定性 BUY_YES 仍可能在临近到期和快速回撤中受损；重启前应提高远离 strike 要求，并限制 BTC 正回落时入场。"
        ),
        "ultra_certainty_above_below_no": (
            "超高确定性 BUY_NO 是薄利微型探测；若亏损，应提高最小净 edge 或要求 BTC 更远离 strike，不能扩大仓位。"
        ),
        "ultra_certainty_above_below_yes": (
            "超高确定性 BUY_YES 是薄利微型探测；若亏损，应提高最小净 edge 或距离要求，而不是扩大仓位。"
        ),
        "recovery_above_below_no": (
            "样本恢复 BUY_NO 是为解决长期零成交而设计的小仓探测；若亏损，应扩大 strike 安全带并降低高价 NO 上限，而不是完全关闭样本恢复机制。"
        ),
        "touch_below_no": (
            "touch_below/NO 单笔大亏说明“目标看似安全”仍可能被快速下跌击穿；重启前应要求更大的 target 距离、"
            "BTC 不在加速下跌，并限制临近到期时追高价 NO。"
        ),
        "touch_below_yes": (
            "touch_below/YES 需要价格真正向目标移动的确认；重启前应要求短周期下行动量和可接受入场价同时成立。"
        ),
        "touch_below_discount_yes": (
            "touch_below/YES 折扣看似有正 edge，但最近快速止损说明路径触碰类 YES 的尾部风险很高；"
            "在没有独立路径概率模型前保持停用，不应为了增加开仓数恢复。"
        ),
        "touch_below_momentum_yes": (
            "touch_below/YES 动量探针已出现快速止损；短周期下跌确认不足以抵消盘口和反抽风险，"
            "在没有更强路径概率模型前保持停用。"
        ),
        "above_below_yes": (
            "above_below/YES 在反向行情中容易追高；重启前应要求突破确认、回踩保护和更小探索仓。"
        ),
        "range_bucket_center_yes": (
            "range_bucket 中心探针是新 1USDC 微型家族；只有在获得关闭样本前才可观察，不能直接提升到主策略。"
        ),
    }
    return reasons.get(family, "该探索家族已被亏损表现自动停用；不要为了增加开仓数直接恢复，必须先设计新的入场条件。")


def _probe_performance_actions(probe_rows: list[ProbePerformanceRow]) -> list[StrategyAutotuneRow]:
    actions: list[StrategyAutotuneRow] = []
    for row in probe_rows:
        evidence = (
            f"opened={row.opened_count},closed={row.closed_count},open={row.open_count},"
            f"pnl={row.realized_pnl:.4f},avg={row.average_realized_pnl:.4f},win_rate={row.win_rate:.2%}"
        )
        if row.closed_count >= 10 and row.average_realized_pnl > 0 and row.win_rate >= 0.55:
            actions.append(
                StrategyAutotuneRow(
                    priority=30,
                    scope=f"probe_family/{row.probe_family}",
                    action="keep_probe_active_consider_cautious_promotion",
                    status="positive_probe_evidence",
                    reason="该探索家族已有足够关闭样本且平均盈利为正，可继续保留，并考虑后续小幅提升优先级。",
                    evidence=evidence,
                )
            )
        elif row.open_count > 0 and row.closed_count < 3:
            actions.append(
                StrategyAutotuneRow(
                    priority=50,
                    scope=f"probe_family/{row.probe_family}",
                    action="wait_for_probe_resolution",
                    status="open_probe_pending",
                    reason="该探索家族仍缺少关闭样本，先等待止盈/止损/结算结果，不因浮动状态过早扩大。",
                    evidence=evidence,
                )
            )
    return actions


def _pending_probe_market_actions(
    strategy_rows: list[StrategyReviewRow],
    probe_rows: list[ProbePerformanceRow],
) -> list[StrategyAutotuneRow]:
    pending_by_type: dict[str, list[ProbePerformanceRow]] = {}
    for row in probe_rows:
        if row.open_count > 0 and row.closed_count < 3:
            pending_by_type.setdefault(row.market_type, []).append(row)

    actions: list[StrategyAutotuneRow] = []
    for row in strategy_rows:
        pending = pending_by_type.get(row.market_type, [])
        if not pending or row.positive_edge_skip_count <= 0:
            continue
        families = ",".join(sorted(item.probe_family for item in pending))
        open_count = sum(item.open_count for item in pending)
        closed_count = sum(item.closed_count for item in pending)
        actions.append(
            StrategyAutotuneRow(
                priority=45,
                scope=f"market_type/{row.market_type}/pending_probe",
                action="wait_for_open_probe_resolution_before_expanding_type",
                status="type_probe_pending",
                reason="该类型已有未结算探索仓，同时仍有正 edge 被过滤；下一步先等现有探索仓止盈/止损/结算，再决定是否扩大或重写条件。",
                evidence=(
                    f"families={families},open={open_count},closed={closed_count},"
                    f"positive_edge_skips={row.positive_edge_skip_count},max_edge={row.max_expected_edge:.4f},top_blocker={row.top_blocker}"
                ),
            )
        )
    return actions


def _strategy_review_actions(strategy_rows: list[StrategyReviewRow], context: AutotuneContext) -> list[StrategyAutotuneRow]:
    actions: list[StrategyAutotuneRow] = []
    for row in strategy_rows:
        evidence = (
            f"takers={row.taker_count},probes={row.probe_taker_count},"
            f"positive_edge_skips={row.positive_edge_skip_count},max_edge={row.max_expected_edge:.4f},"
            f"top_blocker={row.top_blocker},zero_taker_streak={context.zero_taker_streak}"
        )
        if row.status == "positive_edge_blocked":
            actions.append(
                StrategyAutotuneRow(
                    priority=20,
                    scope=f"market_type/{row.market_type}",
                    action=row.recommended_action,
                    status=row.status,
                    reason="正 edge 候选持续被过滤，应该设计小仓位专属探测，而不是粗暴放宽主策略。",
                    evidence=evidence,
                )
            )
        elif row.status == "sample_starved" and row.max_expected_edge > 0:
            actions.append(
                StrategyAutotuneRow(
                    priority=35,
                    scope=f"market_type/{row.market_type}",
                    action="review_top_blocker_for_probe_design",
                    status=row.status,
                    reason="该市场类型样本饥饿但存在正 edge，需要复查 top blocker 是否适合专属探索仓。",
                    evidence=evidence,
                )
            )
        elif row.status == "edge_insufficient":
            actions.append(
                StrategyAutotuneRow(
                    priority=70,
                    scope=f"market_type/{row.market_type}",
                    action="do_not_relax_filters_until_edge_improves",
                    status=row.status,
                    reason="主要问题是净优势不足，此时增加开仓会降低样本质量。",
                    evidence=evidence,
                )
            )
        elif row.status == "no_edge_available":
            actions.append(
                StrategyAutotuneRow(
                    priority=75,
                    scope=f"market_type/{row.market_type}",
                    action="do_not_relax_filters_wait_for_positive_edge",
                    status=row.status,
                    reason="该类型近期没有正 expected edge；零成交不是过滤过严，应该等待市场机会或改进信号来源。",
                    evidence=evidence,
                )
            )
    return actions


def _slot_action(context: AutotuneContext) -> StrategyAutotuneRow:
    evidence = (
        f"open_positions={context.open_positions},probe_slots={context.probe_slots},"
        f"open_exposure={context.open_exposure_usdc:.2f},probe_max_exposure={context.probe_max_exposure_usdc:.2f},"
        f"zero_taker_streak={context.zero_taker_streak},probe_zero_run_threshold={context.probe_zero_run_threshold}"
    )
    if context.probe_slots <= 0 and context.zero_taker_streak < context.probe_zero_run_threshold:
        return StrategyAutotuneRow(
            priority=80,
            scope="probe_slots",
            action="wait_for_next_zero_taker_run",
            status="recent_taker_wait",
            reason="最近一轮已有成交，探索仓触发器会等待至少一轮零成交，避免刚开仓后连续追单。",
            evidence=evidence,
        )
    if context.probe_slots <= 0:
        return StrategyAutotuneRow(
            priority=25,
            scope="probe_slots",
            action="wait_for_exits_or_reduce_probe_exposure",
            status="probe_slots_full",
            reason="探索槽位已满，应优先等待退出或降低单笔探索敞口，而不是继续扩大风险。",
            evidence=evidence,
        )
    if context.zero_taker_streak >= 6:
        return StrategyAutotuneRow(
            priority=25,
            scope="probe_slots",
            action="search_probe_candidates_before_next_relaxation",
            status="slots_available_but_no_recent_takers",
            reason="仍有探索槽位但连续多轮无开仓，应复查 positive edge blocker 并设计小仓探测。",
            evidence=evidence,
        )
    return StrategyAutotuneRow(
        priority=80,
        scope="probe_slots",
        action="maintain_current_probe_budget",
        status="slots_available",
        reason="探索槽位和敞口仍可用，当前不需要为了开仓数调整预算。",
        evidence=evidence,
    )
