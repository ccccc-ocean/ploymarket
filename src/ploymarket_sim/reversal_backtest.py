from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from .classifier import classify_market
from .clob import PricePoint
from .config import AppConfig
from .costs import estimate_entry_cost, fee_amount, taker_fee_rate
from .polymarket import Market
from .strategy_profiles import is_tradeable_market, strategy_config_for_market


@dataclass(frozen=True)
class ReversalStrategy:
    name: str
    allow_buy_no: bool
    allow_reversal: bool
    stop_loss_pct: float
    take_profit_pct: float
    cooldown_seconds: int


@dataclass(frozen=True)
class ReversalTrade:
    timestamp: int
    market_id: str
    strategy: str
    action: str
    side: str
    price: float
    notional: float
    fee: float
    slippage: float
    pnl: float
    net_edge: float
    reason: str


@dataclass(frozen=True)
class ReversalMarketResult:
    strategy: str
    market_id: str
    market_type: str
    question: str
    trades: list[ReversalTrade]
    realized_pnl: float
    ending_cash: float


@dataclass(frozen=True)
class ReversalSummaryRow:
    strategy: str
    market_type: str
    market_count: int
    traded_market_count: int
    entry_count: int
    exit_count: int
    win_count: int
    loss_count: int
    win_rate: float
    realized_pnl: float
    total_fees: float
    total_slippage: float
    average_pnl_per_exit: float


@dataclass
class _OpenPosition:
    side: str
    entry_price: float
    shares: float
    cost: float


def default_reversal_strategies() -> list[ReversalStrategy]:
    return [
        ReversalStrategy("YES_ONLY_SL25", allow_buy_no=False, allow_reversal=False, stop_loss_pct=0.25, take_profit_pct=0.35, cooldown_seconds=0),
        ReversalStrategy("YES_NO_SL25", allow_buy_no=True, allow_reversal=False, stop_loss_pct=0.25, take_profit_pct=0.35, cooldown_seconds=0),
        ReversalStrategy("YES_NO_REV_SL25_CD60M", allow_buy_no=True, allow_reversal=True, stop_loss_pct=0.25, take_profit_pct=0.35, cooldown_seconds=3600),
        ReversalStrategy("YES_NO_REV_SL15_CD60M", allow_buy_no=True, allow_reversal=True, stop_loss_pct=0.15, take_profit_pct=0.30, cooldown_seconds=3600),
        ReversalStrategy("YES_NO_REV_SL12_CD60M", allow_buy_no=True, allow_reversal=True, stop_loss_pct=0.12, take_profit_pct=0.25, cooldown_seconds=3600),
    ]


def run_reversal_backtest(
    config: AppConfig,
    market: Market,
    history: list[PricePoint],
    strategy: ReversalStrategy,
) -> ReversalMarketResult:
    if not is_tradeable_market(market):
        return ReversalMarketResult(strategy.name, market.id, classify_market(market).market_type, market.question, [], 0.0, config.risk.starting_cash)

    market_config = strategy_config_for_market(config, market)
    trades: list[ReversalTrade] = []
    cash = market_config.risk.starting_cash
    position: _OpenPosition | None = None
    side_cooldown_until: dict[str, int] = {}

    for index in range(market_config.signal.long_window, len(history)):
        visible_history = history[: index + 1]
        current = visible_history[-1]
        if position is not None:
            exit_now, exit_reason = _exit_reason(position, current.price, strategy)
            if exit_now:
                trade, cash = _exit_trade(config, market, strategy.name, current, position, cash, exit_reason)
                trades.append(trade)
                stopped_side = position.side if exit_reason == "触发实验止损" else ""
                position = None
                if stopped_side:
                    side_cooldown_until[stopped_side] = current.timestamp + strategy.cooldown_seconds
                if strategy.allow_reversal and stopped_side:
                    opposite = "NO" if stopped_side == "YES" else "YES"
                    entry = _entry_trade_if_allowed(
                        config,
                        market,
                        visible_history,
                        strategy,
                        current,
                        cash,
                        opposite,
                        side_cooldown_until,
                        reason=f"{stopped_side} 止损后反转尝试买 {opposite}",
                        ignore_cooldown=True,
                    )
                    if entry is not None:
                        trade, position, cash = entry
                        trades.append(trade)
            continue

        side = _entry_side(config, market, visible_history, strategy)
        if side is None:
            continue
        entry = _entry_trade_if_allowed(
            config,
            market,
            visible_history,
            strategy,
            current,
            cash,
            side,
            side_cooldown_until,
            reason="实验策略信号入场",
            ignore_cooldown=False,
        )
        if entry is not None:
            trade, position, cash = entry
            trades.append(trade)

    if position is not None and history:
        final = history[-1]
        trade, cash = _exit_trade(config, market, strategy.name, final, position, cash, "回测结束平仓")
        trades.append(trade)

    realized_pnl = sum(trade.pnl for trade in trades)
    return ReversalMarketResult(strategy.name, market.id, classify_market(market).market_type, market.question, trades, realized_pnl, cash)


def summarize_reversal_results(results: list[ReversalMarketResult]) -> list[ReversalSummaryRow]:
    rows = []
    keys = sorted({(result.strategy, result.market_type) for result in results})
    keys = [("ALL", "all")] + keys
    for strategy, market_type in keys:
        selected = results
        if strategy != "ALL":
            selected = [result for result in selected if result.strategy == strategy and result.market_type == market_type]
        if not selected:
            continue
        trades = [trade for result in selected for trade in result.trades]
        entries = [trade for trade in trades if trade.action in {"BUY_YES", "BUY_NO"}]
        exits = [trade for trade in trades if trade.action in {"SELL_YES", "SELL_NO", "MARK_TO_MARKET_EXIT"}]
        wins = [trade for trade in exits if trade.pnl > 0]
        losses = [trade for trade in exits if trade.pnl < 0]
        pnl = sum(result.realized_pnl for result in selected)
        rows.append(
            ReversalSummaryRow(
                strategy=strategy,
                market_type=market_type,
                market_count=len(selected),
                traded_market_count=len([result for result in selected if any(trade.action in {"BUY_YES", "BUY_NO"} for trade in result.trades)]),
                entry_count=len(entries),
                exit_count=len(exits),
                win_count=len(wins),
                loss_count=len(losses),
                win_rate=_ratio(len(wins), len(wins) + len(losses)),
                realized_pnl=pnl,
                total_fees=sum(trade.fee for trade in trades),
                total_slippage=sum(trade.slippage for trade in trades),
                average_pnl_per_exit=_ratio(pnl, len(wins) + len(losses)),
            )
        )
    return rows


def write_reversal_trades_csv(results: list[ReversalMarketResult], output_dir: str) -> Path:
    path = Path(output_dir) / "reversal_trades.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "strategy", "market_id", "market_type", "action", "side", "price", "notional", "fee", "slippage", "pnl", "net_edge", "reason", "question"])
        for result in results:
            for trade in result.trades:
                writer.writerow(
                    [
                        trade.timestamp,
                        trade.strategy,
                        trade.market_id,
                        result.market_type,
                        trade.action,
                        trade.side,
                        trade.price,
                        trade.notional,
                        trade.fee,
                        trade.slippage,
                        trade.pnl,
                        trade.net_edge,
                        trade.reason,
                        result.question,
                    ]
                )
    return path


def write_reversal_summary_csv(rows: list[ReversalSummaryRow], output_dir: str) -> Path:
    path = Path(output_dir) / "reversal_summary.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "strategy",
                "market_type",
                "market_count",
                "traded_market_count",
                "entry_count",
                "exit_count",
                "win_count",
                "loss_count",
                "win_rate",
                "realized_pnl",
                "total_fees",
                "total_slippage",
                "average_pnl_per_exit",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.strategy,
                    row.market_type,
                    row.market_count,
                    row.traded_market_count,
                    row.entry_count,
                    row.exit_count,
                    row.win_count,
                    row.loss_count,
                    row.win_rate,
                    row.realized_pnl,
                    row.total_fees,
                    row.total_slippage,
                    row.average_pnl_per_exit,
                ]
            )
    return path


def print_reversal_summary(rows: list[ReversalSummaryRow], path: Path) -> None:
    strategy_rows = [row for row in rows if row.market_type == "price_range_daily"]
    if not strategy_rows:
        print(f"reversal_backtest | rows={len(rows)} | {path}")
        return
    best = max(strategy_rows, key=lambda row: row.realized_pnl)
    worst = min(strategy_rows, key=lambda row: row.realized_pnl)
    print(
        "reversal_backtest | "
        f"rows={len(rows)} | best={best.strategy} pnl={best.realized_pnl:.2f} trades={best.entry_count + best.exit_count} | "
        f"worst={worst.strategy} pnl={worst.realized_pnl:.2f} trades={worst.entry_count + worst.exit_count} | {path}"
    )


def _entry_side(config: AppConfig, market: Market, history: list[PricePoint], strategy: ReversalStrategy) -> str | None:
    market_config = strategy_config_for_market(config, market)
    prices = [point.price for point in history]
    short_avg = mean(prices[-market_config.signal.short_window :])
    long_avg = mean(prices[-market_config.signal.long_window :])
    momentum = short_avg - long_avg
    current_yes = prices[-1]
    yes_edge = _net_edge(config, market, current_yes, momentum)
    no_price = 1.0 - current_yes
    no_edge = _net_edge(config, market, no_price, -momentum)
    if momentum >= market_config.signal.min_momentum and yes_edge >= market_config.signal.min_edge:
        return "YES"
    if strategy.allow_buy_no and -momentum >= market_config.signal.min_momentum and no_edge >= market_config.signal.min_edge:
        return "NO"
    return None


def _entry_trade_if_allowed(
    config: AppConfig,
    market: Market,
    history: list[PricePoint],
    strategy: ReversalStrategy,
    current: PricePoint,
    cash: float,
    side: str,
    side_cooldown_until: dict[str, int],
    reason: str,
    ignore_cooldown: bool,
) -> tuple[ReversalTrade, _OpenPosition, float] | None:
    if not ignore_cooldown and current.timestamp < side_cooldown_until.get(side, 0):
        return None
    price = _side_price(side, current.price)
    if price <= config.risk.min_price or price >= config.risk.max_price:
        return None
    notional = min(config.backtest.trade_size_usdc, cash)
    fee_rate = taker_fee_rate(price, market.effective_taker_fee_rate(config.backtest.taker_fee_rate))
    slippage = notional * config.backtest.slippage_bps / 10_000
    fee = notional * fee_rate
    cost = notional + fee + slippage
    if cost > cash or cost > config.risk.max_position_usdc:
        return None
    execution_price = price * (1 + config.backtest.slippage_bps / 10_000)
    shares = notional / execution_price
    edge = _side_edge(config, market, history, side)
    if edge < strategy_config_for_market(config, market).signal.min_edge:
        return None
    trade = ReversalTrade(current.timestamp, market.id, strategy.name, f"BUY_{side}", side, execution_price, notional, fee, slippage, 0.0, edge, reason)
    return trade, _OpenPosition(side, execution_price, shares, cost), cash - cost


def _exit_reason(position: _OpenPosition, yes_price: float, strategy: ReversalStrategy) -> tuple[bool, str]:
    current_price = _side_price(position.side, yes_price)
    pnl_pct = (current_price - position.entry_price) / position.entry_price
    if pnl_pct <= -strategy.stop_loss_pct:
        return True, "触发实验止损"
    if pnl_pct >= strategy.take_profit_pct:
        return True, "触发实验止盈"
    return False, "继续持有"


def _exit_trade(
    config: AppConfig,
    market: Market,
    strategy_name: str,
    current: PricePoint,
    position: _OpenPosition,
    cash: float,
    reason: str,
) -> tuple[ReversalTrade, float]:
    price = _side_price(position.side, current.price)
    gross_proceeds = position.shares * price
    fee = fee_amount(gross_proceeds, price, market.effective_taker_fee_rate(config.backtest.taker_fee_rate))
    proceeds = gross_proceeds - fee
    pnl = proceeds - position.cost
    action = f"SELL_{position.side}" if reason != "回测结束平仓" else "MARK_TO_MARKET_EXIT"
    trade = ReversalTrade(current.timestamp, market.id, strategy_name, action, position.side, price, proceeds, fee, 0.0, pnl, 0.0, reason)
    return trade, cash + proceeds


def _side_price(side: str, yes_price: float) -> float:
    return yes_price if side == "YES" else max(0.0, 1.0 - yes_price)


def _side_edge(config: AppConfig, market: Market, history: list[PricePoint], side: str) -> float:
    market_config = strategy_config_for_market(config, market)
    prices = [point.price for point in history]
    short_avg = mean(prices[-market_config.signal.short_window :])
    long_avg = mean(prices[-market_config.signal.long_window :])
    momentum = short_avg - long_avg
    price = _side_price(side, prices[-1])
    return _net_edge(config, market, price, momentum if side == "YES" else -momentum)


def _net_edge(config: AppConfig, market: Market, price: float, directional_momentum: float) -> float:
    market_config = strategy_config_for_market(config, market)
    costs = estimate_entry_cost(
        price,
        market.effective_taker_fee_rate(config.backtest.taker_fee_rate),
        config.backtest.slippage_bps,
        market_config.signal.safety_margin,
    )
    return directional_momentum - costs.total_rate


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
