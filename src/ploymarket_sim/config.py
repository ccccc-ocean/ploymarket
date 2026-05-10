from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ApiConfig:
    gamma_base_url: str
    clob_base_url: str
    request_timeout_seconds: int


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
    universe: UniverseConfig
    signal: SignalConfig
    risk: RiskConfig
    backtest: BacktestConfig


def load_config(path: str | Path) -> AppConfig:
    data = parse_simple_toml(Path(path).read_text(encoding="utf-8"))
    return AppConfig(
        api=ApiConfig(**data["api"]),
        cache=CacheConfig(**data["cache"]),
        storage=StorageConfig(**data["storage"]),
        universe=UniverseConfig(**data["universe"]),
        signal=SignalConfig(**data["signal"]),
        risk=RiskConfig(**data["risk"]),
        backtest=BacktestConfig(**data["backtest"]),
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
