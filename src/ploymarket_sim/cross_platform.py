from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .kalshi import KalshiMarket
from .market_rules import extract_usd_strike, infer_strike_direction
from .polymarket import Market


@dataclass(frozen=True)
class NormalizedMarket:
    platform: str
    market_id: str
    question: str
    strike: float | None
    direction: str
    close_date: str
    yes_price: float | None
    no_price: float | None
    volume_24h: float
    liquidity: float


@dataclass(frozen=True)
class CrossPlatformMatch:
    polymarket: NormalizedMarket
    kalshi: NormalizedMarket
    yes_price_diff: float | None
    cheaper_yes_platform: str
    cheaper_no_platform: str
    match_quality: str


def normalize_polymarket_market(market: Market) -> NormalizedMarket:
    return NormalizedMarket(
        platform="polymarket",
        market_id=market.id,
        question=market.question,
        strike=extract_usd_strike(market.question),
        direction=infer_strike_direction(market.question),
        close_date=_question_date_key(market.question) or _date_key(market.end_date),
        yes_price=market.yes_price,
        no_price=market.no_price,
        volume_24h=market.volume_24hr,
        liquidity=market.liquidity,
    )


def normalize_kalshi_market(market: KalshiMarket) -> NormalizedMarket:
    yes_price = market.mid_yes_price
    return NormalizedMarket(
        platform="kalshi",
        market_id=market.ticker,
        question=market.question,
        strike=extract_usd_strike(market.question),
        direction=infer_strike_direction(market.question),
        close_date=_question_date_key(market.question) or _date_key(market.close_time),
        yes_price=yes_price,
        no_price=max(0.0, 1.0 - yes_price) if yes_price is not None else None,
        volume_24h=market.volume_24h,
        liquidity=market.liquidity,
    )


def match_btc_markets(polymarket_markets: list[Market], kalshi_markets: list[KalshiMarket]) -> list[CrossPlatformMatch]:
    poly = [normalize_polymarket_market(market) for market in polymarket_markets]
    kalshi = [normalize_kalshi_market(market) for market in kalshi_markets]
    rows: list[CrossPlatformMatch] = []
    for p_market in poly:
        for k_market in kalshi:
            quality = _match_quality(p_market, k_market)
            if quality == "no_match":
                continue
            rows.append(_build_match(p_market, k_market, quality))
    rows.sort(key=lambda row: (row.match_quality, -abs(row.yes_price_diff or 0.0)))
    return rows


def write_cross_platform_matches_csv(rows: list[CrossPlatformMatch], output_dir: str) -> Path:
    path = Path(output_dir) / "cross_platform_matches.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "polymarket_id",
                "kalshi_ticker",
                "strike",
                "direction",
                "close_date",
                "polymarket_yes",
                "kalshi_yes",
                "yes_price_diff",
                "cheaper_yes_platform",
                "cheaper_no_platform",
                "match_quality",
                "polymarket_question",
                "kalshi_question",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.polymarket.market_id,
                    row.kalshi.market_id,
                    row.polymarket.strike,
                    row.polymarket.direction,
                    row.polymarket.close_date or row.kalshi.close_date,
                    row.polymarket.yes_price,
                    row.kalshi.yes_price,
                    row.yes_price_diff,
                    row.cheaper_yes_platform,
                    row.cheaper_no_platform,
                    row.match_quality,
                    row.polymarket.question,
                    row.kalshi.question,
                ]
            )
    return path


def print_cross_platform_summary(rows: list[CrossPlatformMatch], path: Path) -> None:
    exact = [row for row in rows if row.match_quality == "exact"]
    loose = [row for row in rows if row.match_quality == "loose_date"]
    best = max(rows, key=lambda row: abs(row.yes_price_diff or 0.0), default=None)
    if best is None:
        print(f"cross_platform | matches=0 | exact=0 | loose=0 | {path}")
        return
    print(
        "cross_platform | "
        f"matches={len(rows)} | exact={len(exact)} | loose={len(loose)} | "
        f"best_diff={best.yes_price_diff:.4f} | cheaper_yes={best.cheaper_yes_platform} | "
        f"poly={best.polymarket.market_id} | kalshi={best.kalshi.market_id} | {path}"
    )


def _match_quality(left: NormalizedMarket, right: NormalizedMarket) -> str:
    if left.strike is None or right.strike is None:
        return "no_match"
    if abs(left.strike - right.strike) > 0.01:
        return "no_match"
    if left.direction == "unknown" or right.direction == "unknown":
        return "no_match"
    if left.direction != right.direction:
        return "no_match"
    if left.close_date and right.close_date and left.close_date == right.close_date:
        return "exact"
    if not left.close_date or not right.close_date:
        return "loose_date"
    return "no_match"


def _build_match(left: NormalizedMarket, right: NormalizedMarket, quality: str) -> CrossPlatformMatch:
    diff = None
    cheaper_yes = ""
    cheaper_no = ""
    if left.yes_price is not None and right.yes_price is not None:
        diff = left.yes_price - right.yes_price
        cheaper_yes = "polymarket" if left.yes_price < right.yes_price else "kalshi"
    if left.no_price is not None and right.no_price is not None:
        cheaper_no = "polymarket" if left.no_price < right.no_price else "kalshi"
    return CrossPlatformMatch(left, right, diff, cheaper_yes, cheaper_no, quality)


def _date_key(value: str | None) -> str:
    if not value:
        return ""
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return value[:10]


def _question_date_key(question: str) -> str:
    match = re.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:,\s*(\d{4}))?\b",
        question.lower(),
    )
    if not match:
        return ""
    month = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }[match.group(1)[:3]]
    year = int(match.group(3) or datetime.now(timezone.utc).year)
    day = int(match.group(2))
    return f"{year:04d}-{month:02d}-{day:02d}"
