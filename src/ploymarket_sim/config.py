from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ApiConfig:
    gamma_base_url: str
    clob_base_url: str
    request_timeout_seconds: int
    data_base_url: str = "https://data-api.polymarket.com"


@dataclass(frozen=True)
class CacheConfig:
    enabled: bool
    directory: str
    ttl_seconds: int
    stale_if_error: bool


@dataclass(frozen=True)
class StorageConfig:
    enabled: bool
    sqlite_path: str
    fresh_market_ttl_seconds: int = 900
    fresh_history_ttl_seconds: int = 180


@dataclass(frozen=True)
class BtcPriceConfig:
    provider: str
    base_url: str
    product_id: str
    granularity: str


@dataclass(frozen=True)
class BtcFilterConfig:
    enabled: bool
    lookback_hours: int
    down_threshold: float
    avoid_yes_price_gte: float


@dataclass(frozen=True)
class UniverseConfig:
    keywords: list[str]
    limit: int
    max_pages: int
    order: str
    active: bool
    closed: bool
    min_liquidity: float
    require_orderbook: bool


@dataclass(frozen=True)
class SignalConfig:
    history_interval: str
    history_fidelity_minutes: int
    short_window: int
    long_window: int
    min_momentum: float
    min_edge: float
    safety_margin: float
    buy_below: float
    sell_above: float


@dataclass(frozen=True)
class ExecutionConfig:
    maker_enabled: bool
    maker_price_improvement: float
    maker_min_edge: float
    maker_fee_rate: float
    maker_order_ttl_seconds: int


@dataclass(frozen=True)
class ExecutionStressConfig:
    enabled: bool = True
    adverse_price_moves: list[float] = field(default_factory=lambda: [0.0025, 0.01])
    partial_fill_fractions: list[float] = field(default_factory=lambda: [0.5, 0.25])
    min_surviving_net_edge: float = 0.003
    max_unfilled_fraction: float = 0.5
    operational_failure_pause_seconds: int = 900
    consecutive_failure_circuit_breaker: int = 3


@dataclass(frozen=True)
class RiskConfig:
    starting_cash: float
    max_position_usdc: float
    max_market_exposure_usdc: float
    max_total_exposure_usdc: float
    max_open_positions: int
    daily_loss_limit_usdc: float
    max_drawdown_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    max_spread: float
    min_price: float
    max_price: float
    paper_reentry_cooldown_seconds: int = 3600
    paper_take_profit_reentry_cooldown_seconds: int = 600
    partial_take_profit_pct: float = 0.125
    partial_take_profit_fraction: float = 0.5
    trailing_stop_activation_pct: float = 0.12
    trailing_stop_drawdown_pct: float = 0.06
    paper_full_take_profit_pct: float = 0.25
    paper_reentry_edge_multiplier: float = 2.0
    live_reprice_edge_multiplier: float = 2.0
    target_market_max_distance_pct: float = 0.025
    target_stop_cooldown_seconds: int = 21600
    target_buy_yes_max_price: float = 0.65
    target_buy_no_max_price: float = 0.75
    range_buy_yes_max_price: float = 0.88
    range_buy_no_max_price: float = 0.75
    range_market_safety_band_pct: float = 0.02
    btc_moving_away_return_pct: float = 0.001
    strategy_loss_pause_count: int = 2
    strategy_loss_pause_window_seconds: int = 21600
    readiness_max_drawdown_pct: float = 0.08
    paper_probe_enabled: bool = True
    paper_probe_zero_run_threshold: int = 12
    paper_probe_trade_size_usdc: float = 5.0
    paper_probe_min_edge: float = 0.0015
    paper_probe_max_open_positions: int = 5
    paper_probe_hard_max_open_positions: int = 10
    paper_probe_max_total_exposure_usdc: float = 30.0
    paper_probe_max_new_positions_per_run: int = 3
    btc_candle_max_age_seconds: int = 3600


@dataclass(frozen=True)
class BacktestConfig:
    trade_size_usdc: float
    taker_fee_rate: float
    slippage_bps: int
    output_dir: str


@dataclass(frozen=True)
class AppConfig:
    api: ApiConfig
    cache: CacheConfig
    storage: StorageConfig
    btc_price: BtcPriceConfig
    btc_filter: BtcFilterConfig
    universe: UniverseConfig
    signal: SignalConfig
    execution: ExecutionConfig
    risk: RiskConfig
    backtest: BacktestConfig
    execution_stress: ExecutionStressConfig = field(default_factory=ExecutionStressConfig)


def load_config(path: str | Path) -> AppConfig:
    data = parse_simple_toml(Path(path).read_text(encoding="utf-8"))
    return AppConfig(
        api=ApiConfig(**data["api"]),
        cache=CacheConfig(**data["cache"]),
        storage=StorageConfig(**data["storage"]),
        btc_price=BtcPriceConfig(**data["btc_price"]),
        btc_filter=BtcFilterConfig(**data["btc_filter"]),
        universe=UniverseConfig(**data["universe"]),
        signal=SignalConfig(**data["signal"]),
        execution=ExecutionConfig(**data["execution"]),
        risk=RiskConfig(**data["risk"]),
        backtest=BacktestConfig(**data["backtest"]),
        execution_stress=ExecutionStressConfig(**data.get("execution_stress", {})),
    )


def parse_simple_toml(text: str) -> dict[str, dict[str, Any]]:
    """Parse the small TOML subset used by config/default.toml on Python 3.9."""
    data: dict[str, dict[str, Any]] = {}
    section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            data[section] = {}
            continue
        if section is None or "=" not in line:
            raise ValueError(f"Invalid config line: {raw_line}")
        key, value = [part.strip() for part in line.split("=", 1)]
        data[section][key] = _parse_value(value)
    return data


def _parse_value(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(part.strip()) for part in inner.split(",")]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
