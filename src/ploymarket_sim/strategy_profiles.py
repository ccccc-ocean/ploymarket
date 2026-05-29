from __future__ import annotations

from dataclasses import replace

from .classifier import classify_market
from .config import AppConfig
from .polymarket import Market


TRADEABLE_MARKET_TYPES = {"price_target", "price_range_daily"}


def is_tradeable_market(market: Market) -> bool:
    return classify_market(market).market_type in TRADEABLE_MARKET_TYPES


def strategy_config_for_market(config: AppConfig, market: Market) -> AppConfig:
    if config.signal.history_fidelity_minutes != 5:
        return config

    market_type = classify_market(market).market_type
    if market_type == "price_range_daily":
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
    if market_type == "price_target":
        return replace(
            config,
            signal=replace(
                config.signal,
                short_window=6,
                long_window=24,
                min_momentum=0.01,
                min_edge=0.01,
            ),
        )
    return config
