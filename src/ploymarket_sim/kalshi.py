from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import sys

from .cache import CachePolicy, JsonCache
from .config import AppConfig
from .http import get_json
from .http import HttpError


@dataclass(frozen=True)
class KalshiMarket:
    ticker: str
    event_ticker: str
    title: str
    subtitle: str
    close_time: str | None
    status: str
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    last_price: float | None
    volume_24h: float
    liquidity: float

    @property
    def question(self) -> str:
        text = " ".join(part for part in [self.title, self.subtitle] if part)
        return text or self.ticker

    @property
    def mid_yes_price(self) -> float | None:
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2
        return self.last_price


def discover_kalshi_btc_markets(config: AppConfig, use_cache: bool = True) -> list[KalshiMarket]:
    cache = _cache_from_config(config) if use_cache else None
    markets: list[KalshiMarket] = []
    series_tickers = config.kalshi.series_tickers or [""]
    for series_ticker in series_tickers:
        markets.extend(_discover_series(config, cache, series_ticker))
    return _dedupe(markets)


def _discover_series(config: AppConfig, cache: JsonCache | None, series_ticker: str) -> list[KalshiMarket]:
    markets: list[KalshiMarket] = []
    cursor = ""
    for _page in range(config.kalshi.max_pages):
        try:
            payload = get_json(
                config.kalshi.base_url,
                "/markets",
                {
                    "limit": config.kalshi.limit,
                    "cursor": cursor or None,
                    "status": config.kalshi.status,
                    "series_ticker": series_ticker or None,
                    "mve_filter": "exclude",
                },
                timeout=config.kalshi.request_timeout_seconds,
                cache=cache,
            )
        except HttpError as exc:
            print(f"warning: kalshi market page failed for {series_ticker or 'all'}: {exc}", file=sys.stderr)
            break
        page_markets = [_parse_market(item) for item in payload.get("markets", [])]
        markets.extend(
            market
            for market in page_markets
            if market is not None and _is_btc_market(market) and market.volume_24h >= config.kalshi.min_volume_24h
        )
        cursor = str(payload.get("cursor") or "")
        if not cursor:
            break
    return markets


def _parse_market(item: dict[str, Any]) -> KalshiMarket | None:
    ticker = str(item.get("ticker") or "")
    if not ticker:
        return None
    title = str(item.get("title") or item.get("event_title") or item.get("subtitle") or "")
    subtitle = str(item.get("yes_sub_title") or item.get("subtitle") or "")
    return KalshiMarket(
        ticker=ticker,
        event_ticker=str(item.get("event_ticker") or ""),
        title=title,
        subtitle=subtitle,
        close_time=item.get("close_time"),
        status=str(item.get("status") or ""),
        yes_bid=_parse_price(item.get("yes_bid_dollars") or item.get("yes_bid")),
        yes_ask=_parse_price(item.get("yes_ask_dollars") or item.get("yes_ask")),
        no_bid=_parse_price(item.get("no_bid_dollars") or item.get("no_bid")),
        no_ask=_parse_price(item.get("no_ask_dollars") or item.get("no_ask")),
        last_price=_parse_price(item.get("last_price_dollars") or item.get("last_price")),
        volume_24h=_parse_float(item.get("volume_24h_fp") or item.get("volume_24h") or item.get("volume_fp")),
        liquidity=_parse_float(item.get("liquidity") or item.get("open_interest") or item.get("open_interest_fp")),
    )


def _parse_price(value: Any) -> float | None:
    parsed = _parse_float_or_none(value)
    if parsed is None:
        return None
    if parsed > 1:
        return parsed / 100
    return parsed


def _parse_float(value: Any) -> float:
    parsed = _parse_float_or_none(value)
    return parsed if parsed is not None else 0.0


def _parse_float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_btc_market(market: KalshiMarket) -> bool:
    text = f"{market.ticker} {market.event_ticker} {market.question}".lower()
    return any(term in text for term in ["bitcoin", "btc"])


def _dedupe(markets: list[KalshiMarket]) -> list[KalshiMarket]:
    seen: set[str] = set()
    unique: list[KalshiMarket] = []
    for market in markets:
        if market.ticker in seen:
            continue
        unique.append(market)
        seen.add(market.ticker)
    return unique


def _cache_from_config(config: AppConfig) -> JsonCache:
    return JsonCache(CachePolicy(config.cache.enabled, config.cache.directory, config.cache.ttl_seconds, config.cache.stale_if_error))
