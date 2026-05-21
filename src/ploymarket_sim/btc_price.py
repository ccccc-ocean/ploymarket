from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
from typing import Any

from .cache import CachePolicy, JsonCache
from .config import AppConfig
from .http import get_json


@dataclass(frozen=True)
class BtcCandle:
    timestamp: int
    low: float
    high: float
    open: float
    close: float


def get_btc_candles(config: AppConfig, use_cache: bool = True) -> list[BtcCandle]:
    payload = get_json(
        config.btc_price.base_url,
        f"/api/v3/brokerage/market/products/{config.btc_price.product_id}/candles",
        {"granularity": config.btc_price.granularity},
        timeout=config.api.request_timeout_seconds,
        cache=_cache_from_config(config) if use_cache else None,
    )
    raw_candles = payload.get("candles", payload) if isinstance(payload, dict) else payload
    candles = [_parse_coinbase_candle(item) for item in raw_candles if _parse_coinbase_candle(item) is not None]
    return sorted(candles, key=lambda candle: candle.timestamp)


def load_btc_candles_csv(path: str | Path) -> list[BtcCandle]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        rows = csv.DictReader(file)
        candles = [
            _parse_coinbase_candle(
                {
                    "start": row.get("timestamp"),
                    "low": row.get("low"),
                    "high": row.get("high"),
                    "open": row.get("open"),
                    "close": row.get("close"),
                }
            )
            for row in rows
        ]
    return [candle for candle in candles if candle is not None]


def _parse_coinbase_candle(item: Any) -> BtcCandle | None:
    try:
        if isinstance(item, dict):
            timestamp = item["start"]
            low = item["low"]
            high = item["high"]
            open_price = item["open"]
            close = item["close"]
        else:
            timestamp, low, high, open_price, close = item[:5]
        return BtcCandle(
            timestamp=int(timestamp),
            low=float(low),
            high=float(high),
            open=float(open_price),
            close=float(close),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _cache_from_config(config: AppConfig) -> JsonCache:
    return JsonCache(
        CachePolicy(
            enabled=config.cache.enabled,
            directory=config.cache.directory,
            ttl_seconds=config.cache.ttl_seconds,
            stale_if_error=config.cache.stale_if_error,
        )
    )
