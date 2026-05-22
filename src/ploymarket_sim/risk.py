from __future__ import annotations

from dataclasses import dataclass

from .config import RiskConfig


@dataclass
class Position:
    market_id: str
    token_id: str
    entry_price: float
    shares: float
    notional: float
    side: str = "YES"


@dataclass
class Portfolio:
    cash: float
    peak_equity: float
    daily_realized_pnl: float
    positions: dict[str, Position]

    @classmethod
    def from_starting_cash(cls, starting_cash: float) -> "Portfolio":
        return cls(cash=starting_cash, peak_equity=starting_cash, daily_realized_pnl=0.0, positions={})

    def total_exposure(self) -> float:
        return sum(position.notional for position in self.positions.values())


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


def approve_entry(
    portfolio: Portfolio,
    config: RiskConfig,
    market_id: str,
    price: float,
    notional: float,
    spread: float | None = None,
) -> RiskDecision:
    if price < config.min_price or price > config.max_price:
        return RiskDecision(False, "价格超出允许区间")
    if spread is not None and spread > config.max_spread:
        return RiskDecision(False, "买卖价差过宽")
    if notional > config.max_position_usdc:
        return RiskDecision(False, "单笔仓位超过上限")
    if len(portfolio.positions) >= config.max_open_positions:
        return RiskDecision(False, "持仓数量超过上限")
    if portfolio.daily_realized_pnl <= -config.daily_loss_limit_usdc:
        return RiskDecision(False, "触发日内亏损上限")
    if portfolio.total_exposure() + notional > config.max_total_exposure_usdc:
        return RiskDecision(False, "总风险敞口超过上限")

    market_exposure = sum(
        position.notional for position in portfolio.positions.values() if position.market_id == market_id
    )
    if market_exposure + notional > config.max_market_exposure_usdc:
        return RiskDecision(False, "单市场风险敞口超过上限")

    drawdown = (portfolio.peak_equity - portfolio.cash) / portfolio.peak_equity
    if drawdown >= config.max_drawdown_pct:
        return RiskDecision(False, "账户回撤达到停机阈值")

    return RiskDecision(True, "通过风控")


def should_exit(position: Position, current_price: float, config: RiskConfig) -> tuple[bool, str]:
    pnl_pct = (current_price - position.entry_price) / position.entry_price
    if pnl_pct <= -config.stop_loss_pct:
        return True, "触发止损"
    if pnl_pct >= config.take_profit_pct:
        return True, "触发止盈"
    return False, "继续持有"
