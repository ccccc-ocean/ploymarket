from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cache import CachePolicy, JsonCache
from .config import AppConfig
from .http import get_json


@dataclass(frozen=True)
class PricePoint:
    timestamp: int
    price: float


def get_price_history(config: AppConfig, token_id: str) -> list[PricePoint]:
    payload = get_json(
        config.api.clob_base_url,
        "/prices-history",
        {
            "market": token_id,
            "interval": config.signal.history_interval,
            "fidelity": config.signal.history_fidelity_minutes,
        },
        timeout=config.api.request_timeout_seconds,
        cache=_cache_from_config(config),
    )
    raw_points = payload.get("history", payload) if isinstance(payload, dict) else payload
    return [_parse_point(point) for point in raw_points if _parse_point(point) is not None]


def _parse_point(point: dict[str, Any]) -> PricePoint | None:
    try:
        timestamp = int(point.get("t") or point.get("timestamp"))
        price = float(point.get("p") or point.get("price"))
    except (TypeError, ValueError, AttributeError):
        return None
    if price <= 0:
        return None
    return PricePoint(timestamp=timestamp, price=price)


def _cache_from_config(config: AppConfig) -> JsonCache:
    return JsonCache(
        CachePolicy(
            enabled=config.cache.enabled,
            directory=config.cache.directory,
            ttl_seconds=config.cache.ttl_seconds,
            stale_if_error=config.cache.stale_if_error,
        )
    )
