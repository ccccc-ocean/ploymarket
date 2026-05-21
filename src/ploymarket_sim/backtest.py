from __future__ import annotations

from dataclasses import dataclass, field

from .btc_price import BtcCandle
from .clob import PricePoint
from .config import AppConfig
from .costs import fee_amount, taker_fee_rate
from .execution import ExecutionPlan, plan_execution
from .orders import OrderEvent, canceled_events, lifecycle_events, make_order_id, rejected_events
from .polymarket import Market
from .risk import Portfolio, Position, approve_entry, should_exit
from .signals import build_signal
from .market_rules import latest_btc_candle_at_or_before
from .strategy_profiles import is_tradeable_market, strategy_config_for_market


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


@dataclass(frozen=True)
class PendingMakerOrder:
    order_id: str
    market_id: str
    token_id: str
    limit_price: float
    notional: float
    fee: float
    expires_at: int
    net_edge: float
    reason: str


def backtest_market(
    market: Market,
    history: list[PricePoint],
    config: AppConfig,
    btc_candles: list[BtcCandle] | None = None,
) -> BacktestResult:
    if not is_tradeable_market(market):
        return BacktestResult(market.id, market.question, [], config.risk.starting_cash, 0.0, [])

    config = strategy_config_for_market(config, market)
    portfolio = Portfolio.from_starting_cash(config.risk.starting_cash)
    trades: list[Trade] = []
    order_events: list[OrderEvent] = []
    order_sequence = 0
    token_id = market.yes_token_id
    if token_id is None:
        return BacktestResult(market.id, market.question, trades, portfolio.cash, 0.0, order_events)

    pending_order: PendingMakerOrder | None = None
    for index in range(config.signal.long_window, len(history)):
        visible_history = history[: index + 1]
        current = visible_history[-1]
        position = portfolio.positions.get(market.id)

        if pending_order:
            if current.price <= pending_order.limit_price:
                portfolio.cash -= pending_order.notional + pending_order.fee
                shares = pending_order.notional / pending_order.limit_price
                portfolio.positions[market.id] = Position(
                    market.id,
                    pending_order.token_id,
                    pending_order.limit_price,
                    shares,
                    pending_order.notional + pending_order.fee,
                )
                order_events.append(
                    OrderEvent(
                        current.timestamp,
                        pending_order.order_id,
                        market.id,
                        "buy_yes",
                        "matched",
                        pending_order.limit_price,
                        pending_order.notional,
                        pending_order.reason,
                    )
                )
                order_events.append(
                    OrderEvent(
                        current.timestamp,
                        pending_order.order_id,
                        market.id,
                        "buy_yes",
                        "settled",
                        pending_order.limit_price,
                        pending_order.notional,
                        pending_order.reason,
                    )
                )
                trades.append(
                    Trade(
                        current.timestamp,
                        market.id,
                        "MAKER_BUY_YES",
                        pending_order.limit_price,
                        pending_order.notional,
                        pending_order.fee,
                        0.0,
                        0.0,
                        pending_order.net_edge,
                        pending_order.reason,
                    )
                )
                pending_order = None
                position = portfolio.positions.get(market.id)
            elif current.timestamp >= pending_order.expires_at:
                order_events.extend(
                    canceled_events(
                        current.timestamp,
                        pending_order.order_id,
                        market.id,
                        "buy_yes",
                        pending_order.limit_price,
                        pending_order.notional,
                        "Maker 挂单超过 TTL 未成交，取消",
                    )
                )
                pending_order = None

        if position:
            exit_now, reason = should_exit(position, current.price, config.risk)
            if exit_now:
                order_sequence += 1
                order_id = make_order_id(market.id, current.timestamp, order_sequence)
                gross_proceeds = position.shares * current.price
                fee = fee_amount(gross_proceeds, current.price, market.effective_taker_fee_rate(config.backtest.taker_fee_rate))
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
        if _blocked_by_btc_filter(current, config, btc_candles or []):
            continue
        execution_plan = plan_execution(market, signal, config.signal, config.backtest, config.execution, current.price)
        if execution_plan.mode == "MAKER" and pending_order is None:
            order_sequence += 1
            pending_order = _create_pending_maker_order(
                market,
                token_id,
                current,
                execution_plan,
                portfolio,
                config,
                make_order_id(market.id, current.timestamp, order_sequence),
            )
            if pending_order:
                order_events.extend(
                    [
                        OrderEvent(current.timestamp, pending_order.order_id, market.id, "buy_yes", "created", pending_order.limit_price, pending_order.notional, pending_order.reason),
                        OrderEvent(current.timestamp, pending_order.order_id, market.id, "buy_yes", "submitted", pending_order.limit_price, pending_order.notional, pending_order.reason),
                        OrderEvent(current.timestamp, pending_order.order_id, market.id, "buy_yes", "accepted", pending_order.limit_price, pending_order.notional, pending_order.reason),
                    ]
                )
            continue
        if execution_plan.mode != "TAKER":
            continue

        market_fee_rate = market.effective_taker_fee_rate(config.backtest.taker_fee_rate)
        entry_fee_rate = taker_fee_rate(current.price, market_fee_rate)
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
            trades.append(Trade(current.timestamp, market.id, "REJECTED", execution_price, 0.0, 0.0, 0.0, 0.0, execution_plan.expected_net_edge, decision.reason))
            continue

        shares = notional / execution_price
        portfolio.cash -= total_cash_needed
        portfolio.positions[market.id] = Position(market.id, token_id, execution_price, shares, total_cash_needed)
        order_events.extend(lifecycle_events(current.timestamp, order_id, market.id, "buy_yes", execution_price, notional, execution_plan.reason))
        trades.append(Trade(current.timestamp, market.id, "BUY_YES", execution_price, notional, entry_fee, slippage, 0.0, execution_plan.expected_net_edge, execution_plan.reason))

    if pending_order and history:
        final = history[-1]
        order_events.extend(
            canceled_events(
                final.timestamp,
                pending_order.order_id,
                market.id,
                "buy_yes",
                pending_order.limit_price,
                pending_order.notional,
                "回测结束取消未成交 Maker 挂单",
            )
        )

    position = portfolio.positions.get(market.id)
    if position and history:
        final = history[-1]
        order_sequence += 1
        order_id = make_order_id(market.id, final.timestamp, order_sequence)
        gross_proceeds = position.shares * final.price
        fee = fee_amount(gross_proceeds, final.price, market.effective_taker_fee_rate(config.backtest.taker_fee_rate))
        proceeds = gross_proceeds - fee
        pnl = proceeds - position.notional
        portfolio.cash += proceeds
        portfolio.daily_realized_pnl += pnl
        order_events.extend(lifecycle_events(final.timestamp, order_id, market.id, "sell_yes", final.price, proceeds, "回测结束平仓"))
        trades.append(Trade(final.timestamp, market.id, "MARK_TO_MARKET_EXIT", final.price, proceeds, fee, 0.0, pnl, 0.0, "回测结束平仓"))

    realized_pnl = sum(trade.pnl for trade in trades)
    return BacktestResult(market.id, market.question, trades, portfolio.cash, realized_pnl, order_events)


def _blocked_by_btc_filter(current: PricePoint, config: AppConfig, btc_candles: list[BtcCandle]) -> bool:
    if not config.btc_filter.enabled:
        return False
    if current.price < config.btc_filter.avoid_yes_price_gte:
        return False
    now = _latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    then = _latest_btc_candle_at_or_before(btc_candles, current.timestamp - config.btc_filter.lookback_hours * 3600)
    if now is None or then is None or then.close == 0:
        return False
    btc_return = (now.close - then.close) / then.close
    return btc_return <= config.btc_filter.down_threshold


def _latest_btc_candle_at_or_before(candles: list[BtcCandle], timestamp: int) -> BtcCandle | None:
    return latest_btc_candle_at_or_before(candles, timestamp)


def _create_pending_maker_order(
    market: Market,
    token_id: str,
    current: PricePoint,
    execution_plan: ExecutionPlan,
    portfolio: Portfolio,
    config: AppConfig,
    order_id: str,
) -> PendingMakerOrder | None:
    if execution_plan.limit_price is None:
        return None
    entry_fee_rate = taker_fee_rate(execution_plan.limit_price, config.execution.maker_fee_rate)
    notional = min(config.backtest.trade_size_usdc, portfolio.cash / (1 + entry_fee_rate))
    entry_fee = notional * entry_fee_rate
    total_cash_needed = notional + entry_fee
    decision = approve_entry(portfolio, config.risk, market.id, execution_plan.limit_price, total_cash_needed)
    if not decision.approved:
        return None
    return PendingMakerOrder(
        order_id=order_id,
        market_id=market.id,
        token_id=token_id,
        limit_price=execution_plan.limit_price,
        notional=notional,
        fee=entry_fee,
        expires_at=current.timestamp + config.execution.maker_order_ttl_seconds,
        net_edge=execution_plan.expected_net_edge,
        reason=execution_plan.reason,
    )
