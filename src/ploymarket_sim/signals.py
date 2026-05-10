from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from .clob import PricePoint
from .config import BacktestConfig, SignalConfig
from .costs import estimate_entry_cost
from .polymarket import Market


@dataclass(frozen=True)
class Signal:
    action: str
    confidence: float
    edge: float
    net_edge: float
    reason: str


def build_signal(
    market: Market,
    history: list[PricePoint],
    config: SignalConfig,
    backtest_config: BacktestConfig | None = None,
) -> Signal:
    prices = [point.price for point in history]
    if len(prices) < config.long_window:
        return Signal("HOLD", 0.0, 0.0, 0.0, "价格历史不足，先观察")

    current = prices[-1]
    short_avg = mean(prices[-config.short_window :])
    long_avg = mean(prices[-config.long_window :])
    momentum = short_avg - long_avg
    net_edge = _net_edge(market, momentum, current, config, backtest_config)

    if current >= config.buy_below:
        return Signal("HOLD", 0.0, momentum, net_edge, "YES 价格太接近 1，盈亏比不够")
    if current <= config.sell_above:
        return Signal("HOLD", 0.0, momentum, net_edge, "YES 价格太接近 0，容易被噪音扫损")

    if momentum >= config.min_momentum and net_edge >= config.min_edge:
        confidence = min(1.0, net_edge / (config.min_edge * 3))
        return Signal("BUY_YES", confidence, momentum, net_edge, "扣除费用、滑点和安全边际后仍有正 edge")

    if momentum <= -config.min_momentum and abs(momentum) >= config.min_edge:
        confidence = min(1.0, abs(momentum) / (config.min_edge * 3))
        return Signal("AVOID", confidence, momentum, net_edge, "短期隐含概率转弱")

    return Signal("HOLD", 0.0, momentum, net_edge, "净优势不足，等待更清晰的定价偏差")


def _net_edge(
    market: Market,
    momentum: float,
    price: float,
    signal_config: SignalConfig,
    backtest_config: BacktestConfig | None,
) -> float:
    if backtest_config is None:
        return momentum
    fee_rate = market.effective_taker_fee_rate(backtest_config.taker_fee_rate)
    costs = estimate_entry_cost(
        price,
        fee_rate,
        backtest_config.slippage_bps,
        signal_config.safety_margin,
    )
    return momentum - costs.total_rate
