from __future__ import annotations

from dataclasses import dataclass

from .config import BacktestConfig, ExecutionConfig, SignalConfig
from .costs import estimate_entry_cost
from .polymarket import Market
from .signals import Signal


@dataclass(frozen=True)
class ExecutionPlan:
    mode: str
    side: str
    limit_price: float | None
    expected_fee_rate: float
    expected_net_edge: float
    reason: str


def plan_execution(
    market: Market,
    signal: Signal,
    signal_config: SignalConfig,
    backtest_config: BacktestConfig,
    execution_config: ExecutionConfig,
    current_price: float | None = None,
) -> ExecutionPlan:
    price = current_price if current_price is not None else market.yes_price
    if price is None:
        return ExecutionPlan("SKIP", "", None, 0.0, 0.0, "缺少 YES 价格，无法制定执行计划")

    if signal.action in {"BUY_YES", "BUY_NO"}:
        execution_price = price if signal.action == "BUY_YES" else max(0.0, 1.0 - price)
        fee_rate = market.effective_taker_fee_rate(backtest_config.taker_fee_rate)
        return ExecutionPlan(
            mode="TAKER",
            side=signal.action,
            limit_price=execution_price,
            expected_fee_rate=fee_rate,
            expected_net_edge=signal.net_edge,
            reason="Taker 成本后仍满足最小净优势，允许模拟直接吃单",
        )

    maker_plan = _maker_candidate(price, signal, signal_config, execution_config)
    if maker_plan is not None:
        return maker_plan

    return ExecutionPlan(
        mode="SKIP",
        side="",
        limit_price=None,
        expected_fee_rate=0.0,
        expected_net_edge=signal.net_edge,
        reason="Taker 净优势不足，Maker 条件也未达到，继续观察",
    )


def _maker_candidate(
    price: float,
    signal: Signal,
    signal_config: SignalConfig,
    execution_config: ExecutionConfig,
) -> ExecutionPlan | None:
    if not execution_config.maker_enabled:
        return None
    if signal.action != "HOLD" or signal.edge < signal_config.min_momentum:
        return None
    if price >= signal_config.buy_below or price <= signal_config.sell_above:
        return None

    limit_price = max(0.01, price - execution_config.maker_price_improvement)
    price_improvement = price - limit_price
    costs = estimate_entry_cost(
        limit_price,
        execution_config.maker_fee_rate,
        slippage_bps=0,
        safety_margin=signal_config.safety_margin,
    )
    expected_net_edge = signal.edge + price_improvement - costs.total_rate
    if expected_net_edge < execution_config.maker_min_edge:
        return None

    return ExecutionPlan(
        mode="MAKER",
        side="BUY_YES",
        limit_price=limit_price,
        expected_fee_rate=execution_config.maker_fee_rate,
        expected_net_edge=expected_net_edge,
        reason="Gross edge 为正但 Taker 后不足，改为 Maker 挂单候选等待更好成交价",
    )
