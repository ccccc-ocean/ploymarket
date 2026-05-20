from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostEstimate:
    fee_rate: float
    slippage_rate: float
    safety_margin: float

    @property
    def total_rate(self) -> float:
        return self.fee_rate + self.slippage_rate + self.safety_margin


def taker_fee_rate(price: float, base_fee_rate: float) -> float:
    """Estimate taker fee as a rate on USDC notional."""
    bounded_price = min(max(price, 0.0), 1.0)
    if bounded_price <= 0:
        return 0.0
    return base_fee_rate * (1.0 - bounded_price)


def estimate_entry_cost(
    price: float,
    base_fee_rate: float,
    slippage_bps: int,
    safety_margin: float = 0.0,
) -> CostEstimate:
    return CostEstimate(
        fee_rate=taker_fee_rate(price, base_fee_rate),
        slippage_rate=slippage_bps / 10_000,
        safety_margin=safety_margin,
    )


def fee_amount(notional: float, price: float, base_fee_rate: float) -> float:
    return notional * taker_fee_rate(price, base_fee_rate)


def fee_amount_for_shares(shares: float, price: float, base_fee_rate: float) -> float:
    """Estimate Polymarket taker fee as C * feeRate * p * (1 - p)."""
    bounded_price = min(max(price, 0.0), 1.0)
    return shares * base_fee_rate * bounded_price * (1.0 - bounded_price)
