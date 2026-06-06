from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from .btc_price import BtcCandle
from .clob import PricePoint
from .polymarket import Market
from .storage import Storage


@dataclass(frozen=True)
class AlignmentRow:
    market_id: str
    question: str
    timestamp: int
    horizon_hours: int
    yes_price: float
    future_yes_price: float
    yes_change: float
    btc_close: float
    future_btc_close: float
    btc_return: float
    btc_past_1h_return: float
    btc_past_3h_return: float


@dataclass(frozen=True)
class AlignmentSummary:
    horizon_hours: int
    sample_count: int
    average_yes_change: float
    average_btc_return: float


def build_alignment_rows(
    markets: list[Market],
    storage: Storage,
    btc_candles: list[BtcCandle],
    horizons_hours: list[int],
    max_points_per_market: int | None = None,
) -> list[AlignmentRow]:
    if not btc_candles:
        return []
    sorted_candles = sorted(btc_candles, key=lambda candle: candle.timestamp)
    candle_timestamps = [candle.timestamp for candle in sorted_candles]
    rows: list[AlignmentRow] = []
    for market in markets:
        history = sorted(storage.load_price_history(market.yes_token_id or ""), key=lambda point: point.timestamp)
        if not history:
            continue
        if max_points_per_market is not None and max_points_per_market > 0 and len(history) > max_points_per_market:
            history = history[-max_points_per_market:]
        history_timestamps = [point.timestamp for point in history]
        for point in history:
            btc_now = _latest_candle_at_or_before(sorted_candles, point.timestamp, candle_timestamps)
            btc_past_1h = _latest_candle_at_or_before(sorted_candles, point.timestamp - 3600, candle_timestamps)
            btc_past_3h = _latest_candle_at_or_before(sorted_candles, point.timestamp - 3 * 3600, candle_timestamps)
            if btc_now is None or btc_past_1h is None or btc_past_3h is None:
                continue
            for horizon in horizons_hours:
                target_timestamp = point.timestamp + horizon * 3600
                future_yes = _first_price_at_or_after(history, target_timestamp, history_timestamps)
                future_btc = _first_candle_at_or_after(sorted_candles, target_timestamp, candle_timestamps)
                if future_yes is None or future_btc is None:
                    continue
                rows.append(
                    AlignmentRow(
                        market_id=market.id,
                        question=market.question,
                        timestamp=point.timestamp,
                        horizon_hours=horizon,
                        yes_price=point.price,
                        future_yes_price=future_yes.price,
                        yes_change=future_yes.price - point.price,
                        btc_close=btc_now.close,
                        future_btc_close=future_btc.close,
                        btc_return=(future_btc.close - btc_now.close) / btc_now.close if btc_now.close else 0.0,
                        btc_past_1h_return=(btc_now.close - btc_past_1h.close) / btc_past_1h.close if btc_past_1h.close else 0.0,
                        btc_past_3h_return=(btc_now.close - btc_past_3h.close) / btc_past_3h.close if btc_past_3h.close else 0.0,
                    )
                )
    return rows


def summarize_alignment(rows: list[AlignmentRow]) -> list[AlignmentSummary]:
    summaries = []
    for horizon in sorted({row.horizon_hours for row in rows}):
        horizon_rows = [row for row in rows if row.horizon_hours == horizon]
        summaries.append(
            AlignmentSummary(
                horizon_hours=horizon,
                sample_count=len(horizon_rows),
                average_yes_change=sum(row.yes_change for row in horizon_rows) / len(horizon_rows),
                average_btc_return=sum(row.btc_return for row in horizon_rows) / len(horizon_rows),
            )
        )
    return summaries


def _latest_candle_at_or_before(candles: list[BtcCandle], timestamp: int, timestamps: list[int] | None = None) -> BtcCandle | None:
    candle_timestamps = timestamps if timestamps is not None else [candle.timestamp for candle in candles]
    index = bisect_right(candle_timestamps, timestamp) - 1
    return candles[index] if index >= 0 else None


def _first_candle_at_or_after(candles: list[BtcCandle], timestamp: int, timestamps: list[int] | None = None) -> BtcCandle | None:
    candle_timestamps = timestamps if timestamps is not None else [candle.timestamp for candle in candles]
    index = bisect_left(candle_timestamps, timestamp)
    return candles[index] if index < len(candles) else None


def _first_price_at_or_after(history: list[PricePoint], timestamp: int, timestamps: list[int] | None = None) -> PricePoint | None:
    history_timestamps = timestamps if timestamps is not None else [point.timestamp for point in history]
    index = bisect_left(history_timestamps, timestamp)
    return history[index] if index < len(history) else None
