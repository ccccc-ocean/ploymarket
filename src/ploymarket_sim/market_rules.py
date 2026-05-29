from __future__ import annotations

import re

from .btc_price import BtcCandle
from .classifier import classify_market
from .polymarket import Market


def blocks_btc_strike_entry(
    market: Market,
    timestamp: int,
    btc_candles: list[BtcCandle],
    action: str = "BUY_YES",
    tolerance_pct: float = 0.0015,
) -> tuple[bool, str]:
    if classify_market(market).market_type != "price_range_daily":
        return False, ""
    strike = extract_usd_strike(market.question)
    if strike is None:
        return False, ""
    candle = latest_btc_candle_at_or_before(btc_candles, timestamp)
    if candle is None:
        return True, f"price_range_daily 缺少 BTC 现货确认，暂停 {action}"
    if action != "BUY_YES":
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


def blocks_price_range_entry(
    market: Market,
    action: str,
    timestamp: int,
    btc_candles: list[BtcCandle],
    yes_price: float | None = None,
    buy_yes_max_price: float = 0.88,
    buy_no_max_price: float = 0.75,
    safety_band_pct: float = 0.02,
    moving_away_return_pct: float = 0.001,
) -> tuple[bool, str]:
    if classify_market(market).market_type != "price_range_daily":
        return False, ""
    if action not in {"BUY_YES", "BUY_NO"}:
        return False, ""

    strike = extract_usd_strike(market.question)
    direction = infer_strike_direction(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, timestamp)
    if strike is None or direction == "unknown":
        return True, f"price_range_daily 缺少可识别 strike/方向，暂停 {action}"
    if candle is None or candle.close <= 0:
        return True, f"price_range_daily 缺少 BTC 现货确认，暂停 {action}"

    if yes_price is not None:
        if action == "BUY_YES" and yes_price > buy_yes_max_price:
            return True, f"price_range_daily BUY_YES 价格过高，避免追高: yes={yes_price:.3f}, max={buy_yes_max_price:.3f}"
        if action == "BUY_NO":
            no_price = max(0.0, 1.0 - yes_price)
            if no_price > buy_no_max_price:
                return True, f"price_range_daily BUY_NO 价格过高，避免高价追 NO: no={no_price:.3f}, max={buy_no_max_price:.3f}"

    recent_return = _return_since(btc_candles, timestamp, 15 * 60, candle.close)
    hourly_return = _return_since(btc_candles, timestamp, 60 * 60, candle.close)
    if recent_return is None:
        recent_return = 0.0

    distance_pct = (strike - candle.close) / candle.close
    near_band = abs(distance_pct) <= safety_band_pct
    if direction == "above":
        if action == "BUY_NO" and 0 < distance_pct <= safety_band_pct and recent_return >= moving_away_return_pct:
            return (
                True,
                f"BTC 正接近 above strike，暂停 BUY_NO: BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}, 15m={recent_return:.2%}",
            )
        if (
            action == "BUY_NO"
            and 0 < distance_pct <= safety_band_pct / 2
            and hourly_return is not None
            and hourly_return >= moving_away_return_pct
        ):
            return (
                True,
                f"BTC 1h 正接近 above strike，暂停 BUY_NO: BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}, 1h={hourly_return:.2%}",
            )
        if action == "BUY_YES" and distance_pct > 0 and recent_return <= -moving_away_return_pct:
            return (
                True,
                f"BTC 正远离 above strike，暂停 BUY_YES: BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}, 15m={recent_return:.2%}",
            )
    if direction == "below":
        if action == "BUY_YES" and distance_pct < 0 and recent_return >= moving_away_return_pct:
            return (
                True,
                f"BTC 正远离 below/dip strike，暂停 BUY_YES: BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}, 15m={recent_return:.2%}",
            )
        if action == "BUY_NO" and -safety_band_pct <= distance_pct < 0 and recent_return <= -moving_away_return_pct:
            return (
                True,
                f"BTC 正接近 below strike，暂停 BUY_NO: BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}, 15m={recent_return:.2%}",
            )
    if near_band:
        return False, ""
    return False, ""


def blocks_price_target_entry(
    market: Market,
    action: str,
    timestamp: int,
    btc_candles: list[BtcCandle],
    max_distance_pct: float = 0.03,
    yes_price: float | None = None,
    buy_yes_max_price: float = 0.65,
    buy_no_max_price: float = 0.75,
    moving_away_return_pct: float = 0.001,
) -> tuple[bool, str]:
    classification = classify_market(market).market_type
    if classification not in {"price_target", "price_target_daily"}:
        return False, ""
    if action not in {"BUY_YES", "BUY_NO"}:
        return False, ""

    strike = extract_usd_strike(market.question)
    direction = infer_strike_direction(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, timestamp)
    if strike is None or direction == "unknown":
        return True, "price_target 缺少可识别 strike/方向，暂停 BUY_YES"
    if candle is None or candle.close <= 0:
        return True, "price_target 缺少 BTC 现货确认，暂停 BUY_YES"
    if yes_price is not None:
        if action == "BUY_YES" and yes_price > buy_yes_max_price:
            return True, f"price_target BUY_YES 价格过高，盈亏比不足: yes={yes_price:.3f}, max={buy_yes_max_price:.3f}"
        if action == "BUY_NO":
            no_price = max(0.0, 1.0 - yes_price)
            if no_price > buy_no_max_price:
                return True, f"price_target BUY_NO 价格过高，盈亏比不足: no={no_price:.3f}, max={buy_no_max_price:.3f}"

    distance_pct = (strike - candle.close) / candle.close
    if direction == "above" and action == "BUY_YES" and distance_pct > max_distance_pct:
        return (
            True,
            f"price_target 距离过远，暂停 BUY_YES: BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}, max={max_distance_pct:.2%}",
        )
    if direction == "below" and action == "BUY_YES" and -distance_pct > max_distance_pct:
        return (
            True,
            f"price_target 距离过远，暂停 BUY_YES: BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}, max={max_distance_pct:.2%}",
        )
    if direction == "above" and action == "BUY_NO" and distance_pct <= max_distance_pct:
        return (
            True,
            f"price_target 接近/站上 above strike，暂停 BUY_NO: BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}, max={max_distance_pct:.2%}",
        )
    if direction == "below" and action == "BUY_NO" and -distance_pct <= max_distance_pct:
        return (
            True,
            f"price_target 接近/跌破 below strike，暂停 BUY_NO: BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}, max={max_distance_pct:.2%}",
        )
    recent_return = _return_since(btc_candles, timestamp, 15 * 60, candle.close)
    hourly_return = _return_since(btc_candles, timestamp, 60 * 60, candle.close)
    if recent_return is not None:
        if direction == "above" and action == "BUY_YES" and recent_return <= -moving_away_return_pct:
            return (
                True,
                f"price_target BTC 正远离 above target，暂停 BUY_YES: BTC={candle.close:.2f}, strike={strike:.2f}, 15m={recent_return:.2%}",
            )
        if direction == "below" and action == "BUY_YES" and recent_return >= moving_away_return_pct:
            return (
                True,
                f"price_target BTC 正远离 below/dip target，暂停 BUY_YES: BTC={candle.close:.2f}, strike={strike:.2f}, 15m={recent_return:.2%}",
            )
    if hourly_return is not None:
        if direction == "above" and action == "BUY_YES" and hourly_return <= -moving_away_return_pct:
            return (
                True,
                f"price_target BTC 1h 正远离 above target，暂停 BUY_YES: BTC={candle.close:.2f}, strike={strike:.2f}, 1h={hourly_return:.2%}",
            )
        if direction == "below" and action == "BUY_YES" and hourly_return >= moving_away_return_pct:
            return (
                True,
                f"price_target BTC 1h 正远离 below/dip target，暂停 BUY_YES: BTC={candle.close:.2f}, strike={strike:.2f}, 1h={hourly_return:.2%}",
            )
    return False, ""


def extract_usd_strike(question: str) -> float | None:
    match = re.search(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]+)?)(k)?", question.lower())
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    if match.group(2):
        value *= 1000
    return value


def infer_strike_direction(question: str) -> str:
    text = question.lower()
    if any(term in text for term in ["above", "over", "higher than", "reach", "hit"]):
        return "above"
    if any(term in text for term in ["below", "under", "lower than", "dip", "drop", "fall to"]):
        return "below"
    return "unknown"


def strike_distance_pct(question: str, btc_price: float | None) -> float | None:
    strike = extract_usd_strike(question)
    if strike is None or btc_price is None or btc_price <= 0:
        return None
    return (strike - btc_price) / btc_price


def describe_strike_risk(question: str, btc_price: float | None, far_threshold_pct: float = 0.02) -> str:
    distance = strike_distance_pct(question, btc_price)
    direction = infer_strike_direction(question)
    if distance is None:
        return "no_strike"
    if direction == "above" and distance > far_threshold_pct:
        return "far_above_spot"
    if direction == "below" and distance < -far_threshold_pct:
        return "far_below_spot"
    if abs(distance) <= far_threshold_pct:
        return "near_spot"
    return "in_the_money_or_unclear"


def latest_btc_candle_at_or_before(candles: list[BtcCandle], timestamp: int) -> BtcCandle | None:
    candidates = [candle for candle in candles if candle.timestamp <= timestamp]
    return candidates[-1] if candidates else None


def _return_since(candles: list[BtcCandle], timestamp: int, lookback_seconds: int, current_close: float) -> float | None:
    previous = latest_btc_candle_at_or_before(candles, timestamp - lookback_seconds)
    if previous is None or previous.close == 0:
        return None
    return (current_close - previous.close) / previous.close
