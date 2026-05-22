from __future__ import annotations

from dataclasses import dataclass

from .backtest import BacktestResult, Trade
from .clob import PricePoint
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
        if trade.action in {"BUY_YES", "BUY_NO", "MAKER_BUY_YES"}:
            cash -= trade.notional + trade.fee + trade.slippage
            invested_by_market[trade.market_id] = invested_by_market.get(trade.market_id, 0.0) + trade.notional
        elif trade.action in {"SELL_YES", "SELL_NO", "MARK_TO_MARKET_EXIT"}:
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


def build_mark_to_market_curve(
    results: list[BacktestResult],
    histories_by_market: dict[str, list[PricePoint]],
    config: AppConfig,
) -> list[PortfolioPoint]:
    cash = config.risk.starting_cash
    positions: dict[str, tuple[float, str]] = {}
    latest_prices: dict[str, float] = {}
    peak_equity = cash
    points: list[PortfolioPoint] = []

    for event in _ordered_portfolio_events(results, histories_by_market):
        event_type = event[0]
        timestamp = event[1]
        market_id = event[2]
        trade = event[3] if len(event) > 3 else None
        price_point = event[4] if len(event) > 4 else None

        action = "MARK"
        pnl = 0.0
        fee = 0.0
        slippage = 0.0

        if event_type == "price" and price_point is not None:
            latest_prices[market_id] = price_point.price
        elif event_type == "trade" and trade is not None:
            action = trade.action
            pnl = trade.pnl
            fee = trade.fee
            slippage = trade.slippage
            if trade.action in {"BUY_YES", "BUY_NO", "MAKER_BUY_YES"}:
                cash -= trade.notional + trade.fee + trade.slippage
                side = "NO" if trade.action == "BUY_NO" else "YES"
                existing_shares, _existing_side = positions.get(market_id, (0.0, side))
                positions[market_id] = (existing_shares + trade.notional / trade.price, side)
                latest_prices[market_id] = trade.price if side == "YES" else max(0.0, 1.0 - trade.price)
            elif trade.action in {"SELL_YES", "SELL_NO", "MARK_TO_MARKET_EXIT"}:
                cash += trade.notional
                positions.pop(market_id, None)
                latest_prices[market_id] = trade.price

        if not positions and action == "MARK":
            continue

        invested = sum(
            shares * _side_price(side, latest_prices.get(open_market_id, 0.0))
            for open_market_id, (shares, side) in positions.items()
        )
        equity = cash + invested
        peak_equity = max(peak_equity, equity)
        drawdown = 0.0 if peak_equity == 0 else (peak_equity - equity) / peak_equity
        points.append(
            PortfolioPoint(
                timestamp=timestamp,
                market_id=market_id,
                action=action,
                cash=cash,
                invested=invested,
                equity=equity,
                peak_equity=peak_equity,
                drawdown=drawdown,
                pnl=pnl,
                fee=fee,
                slippage=slippage,
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


def _ordered_portfolio_events(
    results: list[BacktestResult],
    histories_by_market: dict[str, list[PricePoint]],
):
    events = []
    traded_market_ids = {trade.market_id for result in results for trade in result.trades if trade.action != "REJECTED"}
    for market_id in traded_market_ids:
        for point in histories_by_market.get(market_id, []):
            events.append(("price", point.timestamp, market_id, None, point))
    for trade in _ordered_trades(results):
        events.append(("trade", trade.timestamp, trade.market_id, trade, None))
    return sorted(events, key=lambda event: (event[1], 0 if event[0] == "price" else 1, event[2]))


def _side_price(side: str, yes_price: float) -> float:
    return yes_price if side == "YES" else max(0.0, 1.0 - yes_price)
