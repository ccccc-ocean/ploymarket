from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from .clob import PricePoint
from .config import SignalConfig
from .polymarket import Market


@dataclass(frozen=True)
class Signal:
    action: str
    confidence: float
    edge: float
    reason: str


def build_signal(market: Market, history: list[PricePoint], config: SignalConfig) -> Signal:
    prices = [point.price for point in history]
    if len(prices) < config.long_window:
        return Signal("HOLD", 0.0, 0.0, "价格历史不足，先观察")

    current = prices[-1]
    short_avg = mean(prices[-config.short_window :])
    long_avg = mean(prices[-config.long_window :])
    momentum = short_avg - long_avg

    if current >= config.buy_below:
        return Signal("HOLD", 0.0, momentum, "YES 价格太接近 1，盈亏比不够")
    if current <= config.sell_above:
        return Signal("HOLD", 0.0, momentum, "YES 价格太接近 0，容易被噪音扫损")

    if momentum >= config.min_momentum and momentum >= config.min_edge:
        confidence = min(1.0, momentum / (config.min_edge * 3))
        return Signal("BUY_YES", confidence, momentum, "短期隐含概率强于长期均值")

    if momentum <= -config.min_momentum and abs(momentum) >= config.min_edge:
        confidence = min(1.0, abs(momentum) / (config.min_edge * 3))
        return Signal("AVOID", confidence, momentum, "短期隐含概率转弱")

    return Signal("HOLD", 0.0, momentum, "优势不足，等待更清晰的定价偏差")
