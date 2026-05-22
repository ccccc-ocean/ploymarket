from __future__ import annotations

from dataclasses import dataclass

from .btc_price import BtcCandle
from .classifier import classify_market
from .market_rules import extract_usd_strike, infer_strike_direction, latest_btc_candle_at_or_before
from .polymarket import Market
from .signals import Signal


@dataclass(frozen=True)
class BtcRegime:
    label: str
    close: float | None
    return_15m: float | None
    return_1h: float | None
    return_3h: float | None
    range_1h_pct: float | None


def classify_btc_regime(candles: list[BtcCandle], timestamp: int) -> BtcRegime:
    now = latest_btc_candle_at_or_before(candles, timestamp)
    if now is None:
        return BtcRegime("unknown", None, None, None, None, None)

    return_15m = _return_since(candles, timestamp, 15 * 60, now.close)
    return_1h = _return_since(candles, timestamp, 60 * 60, now.close)
    return_3h = _return_since(candles, timestamp, 3 * 60 * 60, now.close)
    range_1h_pct = _range_pct(candles, timestamp, 60 * 60, now.close)

    if _all_present(return_15m, return_1h, return_3h):
        if return_15m > 0 and return_1h >= 0.0025 and return_3h >= 0.004:
            return BtcRegime("uptrend", now.close, return_15m, return_1h, return_3h, range_1h_pct)
        if return_15m < 0 and return_1h <= -0.0025 and return_3h <= -0.004:
            return BtcRegime("downtrend", now.close, return_15m, return_1h, return_3h, range_1h_pct)
        if abs(return_1h) <= 0.0025 and abs(return_3h) <= 0.006:
            return BtcRegime("range_bound", now.close, return_15m, return_1h, return_3h, range_1h_pct)

    if range_1h_pct is not None and range_1h_pct >= 0.015:
        return BtcRegime("volatile", now.close, return_15m, return_1h, return_3h, range_1h_pct)
    return BtcRegime("neutral", now.close, return_15m, return_1h, return_3h, range_1h_pct)


def blocks_directional_entry(
    market: Market,
    signal: Signal,
    candles: list[BtcCandle],
    timestamp: int,
    near_strike_pct: float = 0.005,
) -> tuple[bool, str]:
    if signal.action not in {"BUY_YES", "BUY_NO"}:
        return False, ""
    if classify_market(market).market_type != "price_range_daily":
        return False, ""

    strike = extract_usd_strike(market.question)
    direction = infer_strike_direction(market.question)
    regime = classify_btc_regime(candles, timestamp)
    if strike is None or direction == "unknown" or regime.close is None:
        return False, ""

    distance_to_strike = (strike - regime.close) / regime.close
    near_strike = abs(distance_to_strike) <= near_strike_pct

    if direction == "above":
        if signal.action == "BUY_YES" and regime.label == "downtrend":
            return True, _reason("BUY_YES", regime, "above 市场遇到 BTC 下跌趋势")
        if signal.action == "BUY_YES" and regime.label == "range_bound" and distance_to_strike > 0:
            return True, _reason("BUY_YES", regime, "above strike 上方突破不足，震荡期不追 YES")
        if signal.action == "BUY_NO" and regime.label == "uptrend" and (near_strike or distance_to_strike <= 0):
            return True, _reason("BUY_NO", regime, "BTC 上涨趋势接近或站上 above strike")

    if direction == "below":
        if signal.action == "BUY_YES" and regime.label == "uptrend":
            return True, _reason("BUY_YES", regime, "below 市场遇到 BTC 上涨趋势")
        if signal.action == "BUY_YES" and regime.label == "range_bound" and distance_to_strike < 0:
            return True, _reason("BUY_YES", regime, "below strike 下方突破不足，震荡期不追 YES")
        if signal.action == "BUY_NO" and regime.label == "downtrend" and (near_strike or distance_to_strike >= 0):
            return True, _reason("BUY_NO", regime, "BTC 下跌趋势接近或跌破 below strike")

    return False, ""


def _return_since(candles: list[BtcCandle], timestamp: int, lookback_seconds: int, current_close: float) -> float | None:
    previous = latest_btc_candle_at_or_before(candles, timestamp - lookback_seconds)
    if previous is None or previous.close == 0:
        return None
    return (current_close - previous.close) / previous.close


def _range_pct(candles: list[BtcCandle], timestamp: int, lookback_seconds: int, current_close: float) -> float | None:
    if current_close == 0:
        return None
    window = [candle for candle in candles if timestamp - lookback_seconds <= candle.timestamp <= timestamp]
    if not window:
        return None
    return (max(candle.high for candle in window) - min(candle.low for candle in window)) / current_close


def _all_present(*values: float | None) -> bool:
    return all(value is not None for value in values)


def _reason(action: str, regime: BtcRegime, detail: str) -> str:
    r1h = "n/a" if regime.return_1h is None else f"{regime.return_1h:.2%}"
    r3h = "n/a" if regime.return_3h is None else f"{regime.return_3h:.2%}"
    return f"BTC regime={regime.label} 阻止 {action}: {detail}; 1h={r1h}, 3h={r3h}"
