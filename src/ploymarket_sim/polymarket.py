from __future__ import annotations

from dataclasses import dataclass
import json
import sys
from typing import Any

from .cache import CachePolicy, JsonCache
from .config import AppConfig
from .http import HttpError
from .http import get_json


@dataclass(frozen=True)
class Market:
    id: str
    question: str
    slug: str
    end_date: str | None
    liquidity: float
    volume_24hr: float
    enable_order_book: bool
    outcomes: list[str]
    outcome_prices: list[float]
    clob_token_ids: list[str]

    @property
    def yes_token_id(self) -> str | None:
        for outcome, token_id in zip(self.outcomes, self.clob_token_ids):
            if outcome.lower() == "yes":
                return token_id
        return self.clob_token_ids[0] if self.clob_token_ids else None

    @property
    def yes_price(self) -> float | None:
        for outcome, price in zip(self.outcomes, self.outcome_prices):
            if outcome.lower() == "yes":
                return price
        return self.outcome_prices[0] if self.outcome_prices else None


def discover_btc_markets(config: AppConfig) -> list[Market]:
    cache = _cache_from_config(config)
    markets = _discover_with_search(config, cache)
    markets.extend(_discover_with_market_pages(config, cache))
    return _dedupe(markets)


def _discover_with_search(config: AppConfig, cache: JsonCache) -> list[Market]:
    markets: list[Market] = []
    for keyword in config.universe.keywords:
        try:
            payload = get_json(
                config.api.gamma_base_url,
                "/public-search",
                {
                    "q": keyword,
                    "limit_per_type": min(config.universe.limit, 5),
                    "page": 1,
                    "events_status": "active",
                    "keep_closed_markets": 0,
                    "sort": config.universe.order,
                    "ascending": "false",
                },
                timeout=config.api.request_timeout_seconds,
                cache=cache,
            )
        except HttpError as exc:
            print(f"warning: search failed for {keyword}: {exc}", file=sys.stderr)
            continue
        for event in payload.get("events") or []:
            for item in event.get("markets") or []:
                market = _parse_market(item)
                if market and _is_btc_market(market, config):
                    markets.append(market)
    return markets


def _discover_with_market_pages(config: AppConfig, cache: JsonCache) -> list[Market]:
    markets: list[Market] = []
    for page in range(config.universe.max_pages):
        try:
            payload = get_json(
                config.api.gamma_base_url,
                "/markets",
                {
                    "active": str(config.universe.active).lower(),
                    "closed": str(config.universe.closed).lower(),
                    "limit": config.universe.limit,
                    "offset": page * config.universe.limit,
                    "order": config.universe.order,
                    "ascending": "false",
                },
                timeout=config.api.request_timeout_seconds,
                cache=cache,
            )
        except HttpError as exc:
            print(f"warning: market page {page} failed: {exc}", file=sys.stderr)
            break
        if not payload:
            break
        for item in payload:
            market = _parse_market(item)
            if market and _is_btc_market(market, config):
                markets.append(market)
    return _dedupe(markets)


def _is_btc_market(market: Market, config: AppConfig) -> bool:
    text = f"{market.question} {market.slug}".lower()
    if not any(keyword.lower() in text for keyword in config.universe.keywords):
        return False
    if config.universe.require_orderbook and not market.enable_order_book:
        return False
    if market.liquidity < config.universe.min_liquidity:
        return False
    if not market.yes_token_id or market.yes_price is None:
        return False
    return True


def _parse_market(item: dict[str, Any]) -> Market | None:
    try:
        outcomes = _json_list(item.get("outcomes"))
        prices = [float(value) for value in _json_list(item.get("outcomePrices"))]
        token_ids = [str(value) for value in _json_list(item.get("clobTokenIds"))]
        return Market(
            id=str(item.get("id", "")),
            question=str(item.get("question") or item.get("title") or ""),
            slug=str(item.get("slug", "")),
            end_date=item.get("endDate") or item.get("end_date_iso"),
            liquidity=float(item.get("liquidity") or 0),
            volume_24hr=float(item.get("volume24hr") or item.get("volume_24hr") or 0),
            enable_order_book=bool(item.get("enableOrderBook")),
            outcomes=[str(value) for value in outcomes],
            outcome_prices=prices,
            clob_token_ids=token_ids,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    return []


def _dedupe(markets: list[Market]) -> list[Market]:
    seen: set[str] = set()
    unique: list[Market] = []
    for market in markets:
        key = market.id or market.slug
        if key not in seen:
            unique.append(market)
            seen.add(key)
    return unique


def _cache_from_config(config: AppConfig) -> JsonCache:
    return JsonCache(
        CachePolicy(
            enabled=config.cache.enabled,
            directory=config.cache.directory,
            ttl_seconds=config.cache.ttl_seconds,
            stale_if_error=config.cache.stale_if_error,
        )
    )
