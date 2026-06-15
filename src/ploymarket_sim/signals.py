from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from .classifier import classify_market, is_range_like_market_type, is_target_like_market_type
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
    no_price = max(0.0, 1.0 - current)
    no_net_edge = _net_edge(market, -momentum, no_price, config, backtest_config)

    market_type = classify_market(market).market_type
    buy_yes_min_momentum = config.min_momentum
    buy_yes_min_edge = config.min_edge
    # Critical #1: re-enable BUY_YES on above_below_expiry / target-like markets
    # so the ×2/×3 thresholds below stop being dead code. BUY_NO thresholds are
    # intentionally NOT mirrored here — the existing BUY_NO regression suite
    # already validates that real BTC weakness must remain tradeable; symmetry
    # tightening should follow once we have live evidence of BUY_NO over-firing.
    allow_buy_yes = (
        market_type in {"up_down_short_term", "above_below_expiry"}
        or is_target_like_market_type(market_type)
    )
    allow_buy_no = market_type in {"up_down_short_term", "above_below_expiry", "touch_above"}
    if market_type == "above_below_expiry":
        buy_yes_min_momentum *= 2
        buy_yes_min_edge *= 3
    if is_target_like_market_type(market_type):
        buy_yes_min_momentum *= 3
        buy_yes_min_edge *= 3

    if allow_buy_yes and momentum >= buy_yes_min_momentum and net_edge >= buy_yes_min_edge:
        if current >= config.buy_below:
            return Signal("HOLD", 0.0, momentum, net_edge, "YES 价格太接近 1，盈亏比不够")
        if current <= config.sell_above:
            return Signal("HOLD", 0.0, momentum, net_edge, "YES 价格太接近 0，容易被噪音扫损")
        confidence = min(1.0, net_edge / (buy_yes_min_edge * 3))
        return Signal("BUY_YES", confidence, momentum, net_edge, "扣除费用、滑点和安全边际后仍有强 YES edge")

    if allow_buy_no and (is_range_like_market_type(market_type) or is_target_like_market_type(market_type)) and momentum <= -config.min_momentum and no_net_edge >= config.min_edge:
        if no_price >= config.buy_below:
            return Signal("HOLD", 0.0, -momentum, no_net_edge, "NO 价格太接近 1，盈亏比不够")
        if no_price <= config.sell_above:
            return Signal("HOLD", 0.0, -momentum, no_net_edge, "NO 价格太接近 0，容易被噪音扫损")
        confidence = min(1.0, no_net_edge / (config.min_edge * 3))
        return Signal("BUY_NO", confidence, -momentum, no_net_edge, "YES 动量转弱，NO 扣除成本后仍有正 edge")

    if not allow_buy_yes and momentum >= buy_yes_min_momentum and net_edge >= buy_yes_min_edge:
        return Signal("HOLD", 0.0, momentum, net_edge, f"{market_type} 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单")

    if not allow_buy_no and momentum <= -config.min_momentum and no_net_edge >= config.min_edge:
        return Signal("HOLD", 0.0, -momentum, no_net_edge, f"{market_type} 暂不允许 BUY_NO，当前结构先观察不交易")

    if momentum <= -config.min_momentum and abs(momentum) >= config.min_edge:
        confidence = min(1.0, abs(momentum) / (config.min_edge * 3))
        return Signal("AVOID", confidence, momentum, net_edge, "短期隐含概率转弱")

    return Signal("HOLD", 0.0, momentum, net_edge, "净优势不足，等待更清晰的定价偏差")


def apply_entry_policy(market: Market, signal: Signal, config: SignalConfig) -> Signal:
    if signal.action not in {"BUY_YES", "BUY_NO"}:
        return signal

    market_type = classify_market(market).market_type
    entry_key = f"{market_type}:{signal.action}"
    if config.entry_allowlist and entry_key not in config.entry_allowlist:
        return Signal(
            "HOLD",
            0.0,
            signal.edge,
            signal.net_edge,
            f"入场白名单未包含 {entry_key}，候选策略不交易该方向",
        )
    if signal.net_edge < config.min_entry_net_edge:
        return Signal(
            "HOLD",
            0.0,
            signal.edge,
            signal.net_edge,
            f"候选策略净 edge 不足: net_edge={signal.net_edge:.4f}, required={config.min_entry_net_edge:.4f}",
        )
    return signal


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
