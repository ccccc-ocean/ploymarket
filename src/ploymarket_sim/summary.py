from __future__ import annotations

from dataclasses import dataclass

from .backtest import BacktestResult, Trade
from .classifier import classify_market
from .polymarket import Market


@dataclass(frozen=True)
class BacktestSummary:
    market_id: str
    market_type: str
    taker_fee_rate: float
    question: str
    trade_count: int
    entry_count: int
    exit_count: int
    rejected_count: int
    win_count: int
    loss_count: int
    win_rate: float
    realized_pnl: float
    total_fees: float
    total_slippage: float
    average_pnl: float
    best_trade_pnl: float
    worst_trade_pnl: float
    ending_cash: float


@dataclass(frozen=True)
class AggregateSummary:
    market_type: str
    market_count: int
    traded_market_count: int
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    realized_pnl: float
    total_fees: float
    total_slippage: float
    average_pnl_per_market: float
    average_pnl_per_trade: float


def summarize_market(market: Market, result: BacktestResult) -> BacktestSummary:
    exits = _exit_trades(result.trades)
    wins = [trade for trade in exits if trade.pnl > 0]
    losses = [trade for trade in exits if trade.pnl < 0]
    entry_count = len([trade for trade in result.trades if trade.action == "BUY_YES"])
    rejected_count = len([trade for trade in result.trades if trade.action == "REJECTED"])
    trade_count = entry_count + len(exits)
    pnl_values = [trade.pnl for trade in exits]

    return BacktestSummary(
        market_id=result.market_id,
        market_type=classify_market(market).market_type,
        taker_fee_rate=market.effective_taker_fee_rate(0.0),
        question=result.question,
        trade_count=trade_count,
        entry_count=entry_count,
        exit_count=len(exits),
        rejected_count=rejected_count,
        win_count=len(wins),
        loss_count=len(losses),
        win_rate=_ratio(len(wins), len(exits)),
        realized_pnl=result.realized_pnl,
        total_fees=sum(trade.fee for trade in result.trades),
        total_slippage=sum(trade.slippage for trade in result.trades),
        average_pnl=_average(pnl_values),
        best_trade_pnl=max(pnl_values, default=0.0),
        worst_trade_pnl=min(pnl_values, default=0.0),
        ending_cash=result.ending_cash,
    )


def aggregate_summaries(summaries: list[BacktestSummary]) -> list[AggregateSummary]:
    market_types = sorted({summary.market_type for summary in summaries})
    return [_aggregate_for_type(market_type, summaries) for market_type in market_types]


def summarize_all(summaries: list[BacktestSummary]) -> AggregateSummary:
    return _aggregate_for_type("all", summaries)


def _aggregate_for_type(market_type: str, summaries: list[BacktestSummary]) -> AggregateSummary:
    selected = summaries if market_type == "all" else [summary for summary in summaries if summary.market_type == market_type]
    trade_count = sum(summary.trade_count for summary in selected)
    win_count = sum(summary.win_count for summary in selected)
    loss_count = sum(summary.loss_count for summary in selected)
    realized_pnl = sum(summary.realized_pnl for summary in selected)

    return AggregateSummary(
        market_type=market_type,
        market_count=len(selected),
        traded_market_count=len([summary for summary in selected if summary.entry_count > 0]),
        trade_count=trade_count,
        win_count=win_count,
        loss_count=loss_count,
        win_rate=_ratio(win_count, win_count + loss_count),
        realized_pnl=realized_pnl,
        total_fees=sum(summary.total_fees for summary in selected),
        total_slippage=sum(summary.total_slippage for summary in selected),
        average_pnl_per_market=_ratio(realized_pnl, len(selected)),
        average_pnl_per_trade=_ratio(realized_pnl, win_count + loss_count),
    )


def _exit_trades(trades: list[Trade]) -> list[Trade]:
    return [trade for trade in trades if trade.action in {"SELL_YES", "MARK_TO_MARKET_EXIT"}]


def _average(values: list[float]) -> float:
    return _ratio(sum(values), len(values))


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
