from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


OrderStatus = Literal["created", "submitted", "accepted", "matched", "settled", "rejected", "failed", "canceled"]
OrderSide = Literal["buy_yes", "sell_yes", "buy_no", "sell_no"]


@dataclass(frozen=True)
class OrderEvent:
    timestamp: int
    order_id: str
    market_id: str
    side: OrderSide
    status: OrderStatus
    price: float
    notional: float
    reason: str


def lifecycle_events(
    timestamp: int,
    order_id: str,
    market_id: str,
    side: OrderSide,
    price: float,
    notional: float,
    reason: str,
) -> list[OrderEvent]:
    return [
        OrderEvent(timestamp, order_id, market_id, side, "created", price, notional, reason),
        OrderEvent(timestamp, order_id, market_id, side, "submitted", price, notional, reason),
        OrderEvent(timestamp, order_id, market_id, side, "accepted", price, notional, reason),
        OrderEvent(timestamp, order_id, market_id, side, "matched", price, notional, reason),
        OrderEvent(timestamp, order_id, market_id, side, "settled", price, notional, reason),
    ]


def rejected_events(
    timestamp: int,
    order_id: str,
    market_id: str,
    side: OrderSide,
    price: float,
    notional: float,
    reason: str,
) -> list[OrderEvent]:
    return [
        OrderEvent(timestamp, order_id, market_id, side, "created", price, notional, reason),
        OrderEvent(timestamp, order_id, market_id, side, "rejected", price, notional, reason),
    ]


def canceled_events(
    timestamp: int,
    order_id: str,
    market_id: str,
    side: OrderSide,
    price: float,
    notional: float,
    reason: str,
) -> list[OrderEvent]:
    return [
        OrderEvent(timestamp, order_id, market_id, side, "canceled", price, notional, reason),
    ]


def make_order_id(market_id: str, timestamp: int, sequence: int) -> str:
    return f"{market_id}-{timestamp}-{sequence}"
