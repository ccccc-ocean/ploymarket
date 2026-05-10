from __future__ import annotations

import csv
from pathlib import Path

from .backtest import BacktestResult
from .classifier import classify_market
from .polymarket import Market
from .signals import Signal
from .summary import AggregateSummary, BacktestSummary


def print_market_table(markets: list[Market]) -> None:
    print(f"found {len(markets)} BTC-related markets")
    for market in markets:
        classification = classify_market(market)
        print(
            f"- {market.id} | yes={market.yes_price:.3f} | liq={market.liquidity:.0f} | "
            f"vol24h={market.volume_24hr:.0f} | type={classification.market_type} | {market.question}"
        )


def print_signal(market: Market, signal: Signal) -> None:
    classification = classify_market(market)
    print(
        f"{market.id} | {classification.market_type} | {signal.action} | gross_edge={signal.edge:.4f} | "
        f"net_edge={signal.net_edge:.4f} | confidence={signal.confidence:.2f}"
    )
    print(f"  {market.question}")
    print(f"  reason: {signal.reason}")


def write_backtest_csv(result: BacktestResult, output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"backtest_{result.market_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "market_id", "action", "price", "notional", "fee", "slippage", "pnl", "net_edge", "reason"])
        for trade in result.trades:
            writer.writerow(
                [
                    trade.timestamp,
                    trade.market_id,
                    trade.action,
                    trade.price,
                    trade.notional,
                    trade.fee,
                    trade.slippage,
                    trade.pnl,
                    trade.net_edge,
                    trade.reason,
                ]
            )
    return path


def write_summary_csv(summaries: list[BacktestSummary], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "backtest_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_id",
                "market_type",
                "trade_count",
                "entry_count",
                "exit_count",
                "rejected_count",
                "win_count",
                "loss_count",
                "win_rate",
                "realized_pnl",
                "total_fees",
                "total_slippage",
                "average_pnl",
                "best_trade_pnl",
                "worst_trade_pnl",
                "ending_cash",
                "question",
            ]
        )
        for summary in summaries:
            writer.writerow(
                [
                    summary.market_id,
                    summary.market_type,
                    summary.trade_count,
                    summary.entry_count,
                    summary.exit_count,
                    summary.rejected_count,
                    summary.win_count,
                    summary.loss_count,
                    summary.win_rate,
                    summary.realized_pnl,
                    summary.total_fees,
                    summary.total_slippage,
                    summary.average_pnl,
                    summary.best_trade_pnl,
                    summary.worst_trade_pnl,
                    summary.ending_cash,
                    summary.question,
                ]
            )
    return path


def write_aggregate_summary_csv(summaries: list[AggregateSummary], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "backtest_summary_by_type.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_type",
                "market_count",
                "traded_market_count",
                "trade_count",
                "win_count",
                "loss_count",
                "win_rate",
                "realized_pnl",
                "total_fees",
                "total_slippage",
                "average_pnl_per_market",
                "average_pnl_per_trade",
            ]
        )
        for summary in summaries:
            writer.writerow(
                [
                    summary.market_type,
                    summary.market_count,
                    summary.traded_market_count,
                    summary.trade_count,
                    summary.win_count,
                    summary.loss_count,
                    summary.win_rate,
                    summary.realized_pnl,
                    summary.total_fees,
                    summary.total_slippage,
                    summary.average_pnl_per_market,
                    summary.average_pnl_per_trade,
                ]
            )
    return path


def print_aggregate_summary(summary: AggregateSummary) -> None:
    print(
        f"summary[{summary.market_type}] | markets={summary.market_count} | traded={summary.traded_market_count} | "
        f"trades={summary.trade_count} | win_rate={summary.win_rate:.1%} | pnl={summary.realized_pnl:.2f} | "
        f"fees={summary.total_fees:.2f} | slippage={summary.total_slippage:.2f}"
    )
