from __future__ import annotations

from dataclasses import dataclass

from .clob import PricePoint
from .config import AppConfig
from .polymarket import Market
from .risk import Portfolio, Position, approve_entry, should_exit
from .signals import build_signal


@dataclass(frozen=True)
class Trade:
    timestamp: int
    market_id: str
    action: str
    price: float
    notional: float
    pnl: float
    reason: str


@dataclass(frozen=True)
class BacktestResult:
    market_id: str
    question: str
    trades: list[Trade]
    ending_cash: float
    realized_pnl: float


def backtest_market(market: Market, history: list[PricePoint], config: AppConfig) -> BacktestResult:
    portfolio = Portfolio.from_starting_cash(config.risk.starting_cash)
    trades: list[Trade] = []
    token_id = market.yes_token_id
    if token_id is None:
        return BacktestResult(market.id, market.question, trades, portfolio.cash, 0.0)

    for index in range(config.signal.long_window, len(history)):
        visible_history = history[: index + 1]
        current = visible_history[-1]
        position = portfolio.positions.get(market.id)

        if position:
            exit_now, reason = should_exit(position, current.price, config.risk)
            if exit_now:
                proceeds = position.shares * current.price * (1 - config.backtest.fee_rate)
                pnl = proceeds - position.notional
                portfolio.cash += proceeds
                portfolio.daily_realized_pnl += pnl
                portfolio.peak_equity = max(portfolio.peak_equity, portfolio.cash)
                del portfolio.positions[market.id]
                trades.append(Trade(current.timestamp, market.id, "SELL_YES", current.price, proceeds, pnl, reason))
            continue

        signal = build_signal(market, visible_history, config.signal)
        if signal.action != "BUY_YES":
            continue

        notional = min(config.backtest.trade_size_usdc, portfolio.cash)
        execution_price = current.price * (1 + config.backtest.slippage_bps / 10_000)
        decision = approve_entry(portfolio, config.risk, market.id, execution_price, notional)
        if not decision.approved:
            trades.append(Trade(current.timestamp, market.id, "REJECTED", execution_price, 0.0, 0.0, decision.reason))
            continue

        shares = notional / execution_price
        portfolio.cash -= notional
        portfolio.positions[market.id] = Position(market.id, token_id, execution_price, shares, notional)
        trades.append(Trade(current.timestamp, market.id, "BUY_YES", execution_price, notional, 0.0, signal.reason))

    position = portfolio.positions.get(market.id)
    if position and history:
        final = history[-1]
        proceeds = position.shares * final.price * (1 - config.backtest.fee_rate)
        pnl = proceeds - position.notional
        portfolio.cash += proceeds
        portfolio.daily_realized_pnl += pnl
        trades.append(Trade(final.timestamp, market.id, "MARK_TO_MARKET_EXIT", final.price, proceeds, pnl, "回测结束平仓"))

    realized_pnl = sum(trade.pnl for trade in trades)
    return BacktestResult(market.id, market.question, trades, portfolio.cash, realized_pnl)
