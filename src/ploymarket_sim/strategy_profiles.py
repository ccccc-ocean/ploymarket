from __future__ import annotations

from dataclasses import replace

from .classifier import classify_market, is_range_like_market_type, is_target_like_market_type
from .config import AppConfig
from .polymarket import Market


TRADEABLE_MARKET_TYPES = {
    "up_down_short_term",
    "above_below_expiry",
    "touch_above",
    "touch_below",
    "expiry_target",
}


def is_tradeable_market(market: Market) -> bool:
    return classify_market(market).market_type in TRADEABLE_MARKET_TYPES


def strategy_config_for_market(config: AppConfig, market: Market) -> AppConfig:
    if config.signal.history_fidelity_minutes != 5:
        return config

    market_type = classify_market(market).market_type
    if market_type == "up_down_short_term":
        return replace(
            config,
            signal=replace(
                config.signal,
                short_window=3,
                long_window=12,
                min_momentum=0.004,
                min_edge=0.003,
            ),
        )
    if market_type == "above_below_expiry":
        return replace(
            config,
            signal=replace(
                config.signal,
                short_window=36,
                long_window=144,
                min_momentum=0.0025,
                min_edge=0.0015,
            ),
        )
    if market_type == "range_bucket":
        return replace(
            config,
            signal=replace(
                config.signal,
                short_window=12,
                long_window=48,
                min_momentum=0.012,
                min_edge=0.010,
            ),
        )
    if market_type == "expiry_target":
        return replace(
            config,
            signal=replace(
                config.signal,
                short_window=4,
                long_window=18,
                min_momentum=0.015,
                min_edge=0.015,
            ),
        )
    if is_target_like_market_type(market_type):
        return replace(
            config,
            signal=replace(
                config.signal,
                short_window=6,
                long_window=24,
                min_momentum=0.02,
                min_edge=0.02,
            ),
        )
    if is_range_like_market_type(market_type):
        return config
    return config
