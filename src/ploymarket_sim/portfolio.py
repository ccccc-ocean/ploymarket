from __future__ import annotations

from dataclasses import dataclass

from .backtest import BacktestResult, Trade
from .config import AppConfig


@dataclass(frozen=True)
class PortfolioPoint:
    timestamp: int
    market_id: str
    action: str
    cash: float
    invested: float
    equity: float
    peak_equity: float
    drawdown: float
    pnl: float
    fee: float
    slippage: float


@dataclass(frozen=True)
class PortfolioSummary:
    starting_cash: float
    ending_equity: float
    realized_pnl: float
    total_fees: float
    total_slippage: float
    max_drawdown: float
    event_count: int


def build_portfolio_curve(results: list[BacktestResult], config: AppConfig) -> list[PortfolioPoint]:
    cash = config.risk.starting_cash
    invested_by_market: dict[str, float] = {}
    peak_equity = cash
    points: list[PortfolioPoint] = []

    for trade in _ordered_trades(results):
        if trade.action == "BUY_YES":
            cash -= trade.notional + trade.fee + trade.slippage
            invested_by_market[trade.market_id] = invested_by_market.get(trade.market_id, 0.0) + trade.notional
        elif trade.action in {"SELL_YES", "MARK_TO_MARKET_EXIT"}:
            cash += trade.notional
            invested_by_market.pop(trade.market_id, None)
        elif trade.action == "REJECTED":
            pass

        invested = sum(invested_by_market.values())
        equity = cash + invested
        peak_equity = max(peak_equity, equity)
        drawdown = 0.0 if peak_equity == 0 else (peak_equity - equity) / peak_equity
        points.append(
            PortfolioPoint(
                timestamp=trade.timestamp,
                market_id=trade.market_id,
                action=trade.action,
                cash=cash,
                invested=invested,
                equity=equity,
                peak_equity=peak_equity,
                drawdown=drawdown,
                pnl=trade.pnl,
                fee=trade.fee,
                slippage=trade.slippage,
            )
        )

    return points


def summarize_portfolio(points: list[PortfolioPoint], config: AppConfig) -> PortfolioSummary:
    ending_equity = points[-1].equity if points else config.risk.starting_cash
    return PortfolioSummary(
        starting_cash=config.risk.starting_cash,
        ending_equity=ending_equity,
        realized_pnl=ending_equity - config.risk.starting_cash,
        total_fees=sum(point.fee for point in points),
        total_slippage=sum(point.slippage for point in points),
        max_drawdown=max((point.drawdown for point in points), default=0.0),
        event_count=len(points),
    )


def _ordered_trades(results: list[BacktestResult]) -> list[Trade]:
    trades = [trade for result in results for trade in result.trades if trade.action != "REJECTED"]
    return sorted(trades, key=lambda trade: (trade.timestamp, trade.market_id, trade.action))
