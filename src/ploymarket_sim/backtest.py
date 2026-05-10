from __future__ import annotations

from dataclasses import dataclass, field

from .clob import PricePoint
from .config import AppConfig
from .costs import fee_amount, taker_fee_rate
from .orders import OrderEvent, lifecycle_events, make_order_id, rejected_events
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
    fee: float
    slippage: float
    pnl: float
    net_edge: float
    reason: str


@dataclass(frozen=True)
class BacktestResult:
    market_id: str
    question: str
    trades: list[Trade]
    ending_cash: float
    realized_pnl: float
    order_events: list[OrderEvent] = field(default_factory=list)


def backtest_market(market: Market, history: list[PricePoint], config: AppConfig) -> BacktestResult:
    portfolio = Portfolio.from_starting_cash(config.risk.starting_cash)
    trades: list[Trade] = []
    order_events: list[OrderEvent] = []
    order_sequence = 0
    token_id = market.yes_token_id
    if token_id is None:
        return BacktestResult(market.id, market.question, trades, portfolio.cash, 0.0, order_events)

    for index in range(config.signal.long_window, len(history)):
        visible_history = history[: index + 1]
        current = visible_history[-1]
        position = portfolio.positions.get(market.id)

        if position:
            exit_now, reason = should_exit(position, current.price, config.risk)
            if exit_now:
                order_sequence += 1
                order_id = make_order_id(market.id, current.timestamp, order_sequence)
                gross_proceeds = position.shares * current.price
                fee = fee_amount(gross_proceeds, current.price, config.backtest.taker_fee_rate)
                proceeds = gross_proceeds - fee
                pnl = proceeds - position.notional
                portfolio.cash += proceeds
                portfolio.daily_realized_pnl += pnl
                portfolio.peak_equity = max(portfolio.peak_equity, portfolio.cash)
                del portfolio.positions[market.id]
                order_events.extend(lifecycle_events(current.timestamp, order_id, market.id, "sell_yes", current.price, proceeds, reason))
                trades.append(Trade(current.timestamp, market.id, "SELL_YES", current.price, proceeds, fee, 0.0, pnl, 0.0, reason))
            continue

        signal = build_signal(market, visible_history, config.signal, config.backtest)
        if signal.action != "BUY_YES":
            continue

        entry_fee_rate = taker_fee_rate(current.price, config.backtest.taker_fee_rate)
        slippage_rate = config.backtest.slippage_bps / 10_000
        notional = min(config.backtest.trade_size_usdc, portfolio.cash / (1 + entry_fee_rate + slippage_rate))
        slippage = notional * slippage_rate
        entry_fee = notional * entry_fee_rate
        total_cash_needed = notional + entry_fee + slippage
        execution_price = current.price * (1 + config.backtest.slippage_bps / 10_000)
        decision = approve_entry(portfolio, config.risk, market.id, execution_price, total_cash_needed)
        order_sequence += 1
        order_id = make_order_id(market.id, current.timestamp, order_sequence)
        if not decision.approved:
            order_events.extend(rejected_events(current.timestamp, order_id, market.id, "buy_yes", execution_price, total_cash_needed, decision.reason))
            trades.append(Trade(current.timestamp, market.id, "REJECTED", execution_price, 0.0, 0.0, 0.0, 0.0, signal.net_edge, decision.reason))
            continue

        shares = notional / execution_price
        portfolio.cash -= total_cash_needed
        portfolio.positions[market.id] = Position(market.id, token_id, execution_price, shares, total_cash_needed)
        order_events.extend(lifecycle_events(current.timestamp, order_id, market.id, "buy_yes", execution_price, notional, signal.reason))
        trades.append(Trade(current.timestamp, market.id, "BUY_YES", execution_price, notional, entry_fee, slippage, 0.0, signal.net_edge, signal.reason))

    position = portfolio.positions.get(market.id)
    if position and history:
        final = history[-1]
        order_sequence += 1
        order_id = make_order_id(market.id, final.timestamp, order_sequence)
        gross_proceeds = position.shares * final.price
        fee = fee_amount(gross_proceeds, final.price, config.backtest.taker_fee_rate)
        proceeds = gross_proceeds - fee
        pnl = proceeds - position.notional
        portfolio.cash += proceeds
        portfolio.daily_realized_pnl += pnl
        order_events.extend(lifecycle_events(final.timestamp, order_id, market.id, "sell_yes", final.price, proceeds, "回测结束平仓"))
        trades.append(Trade(final.timestamp, market.id, "MARK_TO_MARKET_EXIT", final.price, proceeds, fee, 0.0, pnl, 0.0, "回测结束平仓"))

    realized_pnl = sum(trade.pnl for trade in trades)
    return BacktestResult(market.id, market.question, trades, portfolio.cash, realized_pnl, order_events)
