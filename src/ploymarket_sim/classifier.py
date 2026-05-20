from __future__ import annotations

from dataclasses import dataclass
import re

from .polymarket import Market


MARKET_TYPES = [
    "price_target",
    "price_target_daily",
    "price_range_daily",
    "company_treasury",
    "indirect_event",
    "unknown",
]


@dataclass(frozen=True)
class MarketClassification:
    market_type: str
    reason: str


def classify_market(market: Market) -> MarketClassification:
    text = f"{market.question} {market.slug}".lower()

    if _has_any(text, ["microstrategy", "strategy", "mstr", "saylor"]):
        return MarketClassification("company_treasury", "公司 BTC 持仓或公告事件")

    if _has_any(text, ["up or down"]):
        return MarketClassification("price_range_daily", "短周期涨跌方向市场")

    if _has_any(text, ["above", "below"]) and _has_date_hint(text):
        return MarketClassification("price_range_daily", "短周期价格区间市场")

    if _has_any(text, ["reach", "hit", "dip to", "drop to"]) and _has_daily_target_hint(text):
        return MarketClassification("price_target_daily", "单日 BTC 价格目标市场")

    if _has_any(text, ["reach", "hit", "dip to", "drop to"]):
        return MarketClassification("price_target", "BTC 价格目标市场")

    if _has_any(text, ["bitcoin", "btc"]):
        return MarketClassification("indirect_event", "只和 BTC 间接相关")

    return MarketClassification("unknown", "无法用第一版规则分类")


def is_market_type(market: Market, market_type: str) -> bool:
    if market_type == "all":
        return True
    return classify_market(market).market_type == market_type


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
