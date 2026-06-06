from __future__ import annotations

from dataclasses import dataclass
import re

from .polymarket import Market


MARKET_TYPES = [
    "up_down_short_term",
    "above_below_expiry",
    "range_bucket",
    "touch_above",
    "touch_below",
    "expiry_target",
    "company_treasury",
    "indirect_event",
    "unknown",
]

RANGE_LIKE_MARKET_TYPES = {"up_down_short_term", "above_below_expiry", "range_bucket"}
TARGET_LIKE_MARKET_TYPES = {"touch_above", "touch_below", "expiry_target"}


@dataclass(frozen=True)
class MarketClassification:
    market_type: str
    reason: str


def classify_market(market: Market) -> MarketClassification:
    text = f"{market.question} {market.slug}".lower()

    if _has_any(text, ["microstrategy", "strategy", "mstr", "saylor"]):
        return MarketClassification("company_treasury", "公司 BTC 持仓或公告事件")

    if _has_any(text, ["up or down"]):
        return MarketClassification("up_down_short_term", "短周期涨跌方向市场")

    if _is_range_bucket(text):
        return MarketClassification("range_bucket", "BTC 区间落点市场")

    if _has_any(text, ["above", "below"]) and _has_date_hint(text):
        return MarketClassification("above_below_expiry", "到期 above/below 价格市场")

    if _has_any(text, ["reach", "hit", "dip to", "drop to"]) and _has_daily_target_hint(text):
        return MarketClassification("expiry_target", "带明确日期的 BTC 触及目标市场")

    if _has_any(text, ["dip to", "drop to", "fall to"]):
        return MarketClassification("touch_below", "BTC 向下触及目标市场")

    if _has_any(text, ["reach", "hit", "touch"]):
        return MarketClassification("touch_above", "BTC 向上触及目标市场")

    if _has_any(text, ["bitcoin", "btc"]):
        return MarketClassification("indirect_event", "只和 BTC 间接相关")

    return MarketClassification("unknown", "无法用第一版规则分类")


def is_market_type(market: Market, market_type: str) -> bool:
    if market_type == "all":
        return True
    return classify_market(market).market_type == market_type


def is_range_like_market_type(market_type: str) -> bool:
    return market_type in RANGE_LIKE_MARKET_TYPES


def is_target_like_market_type(market_type: str) -> bool:
    return market_type in TARGET_LIKE_MARKET_TYPES


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _has_date_hint(text: str) -> bool:
    month_names = [
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    ]
    return bool(re.search(r"\b\d{1,2}/\d{1,2}\b|\b\d{4}\b", text)) or any(month in text for month in month_names)


def _has_daily_target_hint(text: str) -> bool:
    if re.search(r"\bon\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}\b", text):
        return True
    if re.search(r"\b\d{1,2}/\d{1,2}\b", text):
        return True
    return False


def _is_range_bucket(text: str) -> bool:
    if "between" in text and re.search(r"\$\s*[0-9,]+(?:k)?\s+and\s+\$\s*[0-9,]+(?:k)?", text):
        return True
    if re.search(r"\$\s*[0-9,]+(?:k)?\s*-\s*\$\s*[0-9,]+(?:k)?", text):
        return True
    return False
