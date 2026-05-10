from __future__ import annotations

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
) -> list[AlignmentRow]:
    if not btc_candles:
        return []
    rows: list[AlignmentRow] = []
    for market in markets:
        history = storage.load_price_history(market.yes_token_id or "")
        if not history:
            continue
        for point in history:
            btc_now = _latest_candle_at_or_before(btc_candles, point.timestamp)
            if btc_now is None:
                continue
            for horizon in horizons_hours:
                target_timestamp = point.timestamp + horizon * 3600
                future_yes = _first_price_at_or_after(history, target_timestamp)
                future_btc = _first_candle_at_or_after(btc_candles, target_timestamp)
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


def _latest_candle_at_or_before(candles: list[BtcCandle], timestamp: int) -> BtcCandle | None:
    candidates = [candle for candle in candles if candle.timestamp <= timestamp]
    return candidates[-1] if candidates else None


def _first_candle_at_or_after(candles: list[BtcCandle], timestamp: int) -> BtcCandle | None:
    for candle in candles:
        if candle.timestamp >= timestamp:
            return candle
    return None


def _first_price_at_or_after(history: list[PricePoint], timestamp: int) -> PricePoint | None:
    for point in history:
        if point.timestamp >= timestamp:
            return point
    return None
