from __future__ import annotations

import re

from .btc_price import BtcCandle
from .classifier import classify_market
from .polymarket import Market


def blocks_btc_strike_entry(market: Market, timestamp: int, btc_candles: list[BtcCandle], tolerance_pct: float = 0.0015) -> tuple[bool, str]:
    if classify_market(market).market_type != "price_range_daily":
        return False, ""
    strike = extract_usd_strike(market.question)
    if strike is None:
        return False, ""
    candle = latest_btc_candle_at_or_before(btc_candles, timestamp)
    if candle is None:
        return False, ""

    text = market.question.lower()
    if "above" in text:
        required = strike * (1 - tolerance_pct)
        if candle.close < required:
            return True, f"BTC 现货 {candle.close:.2f} 尚未接近 above strike {strike:.2f}"
    if "below" in text:
        required = strike * (1 + tolerance_pct)
        if candle.close > required:
            return True, f"BTC 现货 {candle.close:.2f} 尚未接近 below strike {strike:.2f}"
    return False, ""


def extract_usd_strike(question: str) -> float | None:
    match = re.search(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]+)?)(k)?", question.lower())
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    if match.group(2):
        value *= 1000
    return value


def latest_btc_candle_at_or_before(candles: list[BtcCandle], timestamp: int) -> BtcCandle | None:
    candidates = [candle for candle in candles if candle.timestamp <= timestamp]
    return candidates[-1] if candidates else None
