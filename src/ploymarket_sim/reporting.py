from __future__ import annotations

import csv
from pathlib import Path

from .backtest import BacktestResult
from .classifier import classify_market
from .portfolio import PortfolioPoint, PortfolioSummary
from .paper import PaperSignalRow
from .paper_report import PaperRunSummary
from .polymarket import Market
from .signals import Signal
from .storage import MarketHistoryStats
from .summary import AggregateSummary, BacktestSummary


def print_market_table(markets: list[Market]) -> None:
    print(f"found {len(markets)} BTC-related markets")
    for market in markets:
        classification = classify_market(market)
        fee_label = f"{market.taker_fee_rate:.3f}" if market.taker_fee_rate is not None else "default"
        print(
            f"- {market.id} | yes={market.yes_price:.3f} | liq={market.liquidity:.0f} | "
            f"vol24h={market.volume_24hr:.0f} | type={classification.market_type} | fee={fee_label} | {market.question}"
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


def write_order_events_csv(result: BacktestResult, output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"orders_{result.market_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "order_id", "market_id", "side", "status", "price", "notional", "reason"])
        for event in result.order_events:
            writer.writerow(
                [
                    event.timestamp,
                    event.order_id,
                    event.market_id,
                    event.side,
                    event.status,
                    event.price,
                    event.notional,
                    event.reason,
                ]
            )
    return path


def write_all_order_events_csv(results: list[BacktestResult], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "orders_all.csv"
    events = [event for result in results for event in result.order_events]
    events.sort(key=lambda event: (event.timestamp, event.order_id, _order_status_rank(event.status)))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "order_id", "market_id", "side", "status", "price", "notional", "reason"])
        for event in events:
            writer.writerow(
                [
                    event.timestamp,
                    event.order_id,
                    event.market_id,
                    event.side,
                    event.status,
                    event.price,
                    event.notional,
                    event.reason,
                ]
            )
    return path


def _order_status_rank(status: str) -> int:
    ranks = {
        "created": 0,
        "submitted": 1,
        "accepted": 2,
        "matched": 3,
        "settled": 4,
        "rejected": 5,
        "failed": 6,
        "canceled": 7,
    }
    return ranks.get(status, 99)


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
                "taker_fee_rate",
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
                    summary.taker_fee_rate,
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


def write_portfolio_curve_csv(points: list[PortfolioPoint], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "portfolio_curve.csv"
    _write_portfolio_points(path, points)
    return path


def write_mark_to_market_curve_csv(points: list[PortfolioPoint], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "portfolio_mtm_curve.csv"
    _write_portfolio_points(path, points)
    return path


def write_portfolio_summary_csv(summary: PortfolioSummary, output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "portfolio_summary.csv"
    _write_portfolio_summary(path, summary)
    return path


def write_mark_to_market_summary_csv(summary: PortfolioSummary, output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "portfolio_mtm_summary.csv"
    _write_portfolio_summary(path, summary)
    return path


def print_portfolio_summary(summary: PortfolioSummary) -> None:
    print(
        f"portfolio | ending_equity={summary.ending_equity:.2f} | pnl={summary.realized_pnl:.2f} | "
        f"max_drawdown={summary.max_drawdown:.1%} | fees={summary.total_fees:.2f} | "
        f"slippage={summary.total_slippage:.2f} | events={summary.event_count}"
    )


def write_paper_signal_rows_csv(rows: list[PaperSignalRow], output_dir: str, run_timestamp: int) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"paper_run_{run_timestamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "run_timestamp",
                "market_id",
                "market_type",
                "question",
                "yes_price",
                "taker_fee_rate",
                "action",
                "confidence",
                "gross_edge",
                "net_edge",
                "reason",
                "execution_mode",
                "execution_side",
                "limit_price",
                "expected_net_edge",
                "execution_reason",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.run_timestamp,
                    row.market_id,
                    row.market_type,
                    row.question,
                    row.yes_price,
                    row.taker_fee_rate,
                    row.action,
                    row.confidence,
                    row.gross_edge,
                    row.net_edge,
                    row.reason,
                    row.execution_mode,
                    row.execution_side,
                    row.limit_price,
                    row.expected_net_edge,
                    row.execution_reason,
                ]
            )
    return path


def write_paper_report_csv(summaries: list[PaperRunSummary], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "paper_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "run_timestamp",
                "market_count",
                "buy_yes_count",
                "hold_count",
                "avoid_count",
                "taker_count",
                "maker_count",
                "skip_count",
                "best_market_id",
                "best_market_type",
                "best_net_edge",
                "best_action",
                "best_execution_mode",
                "best_question",
            ]
        )
        for summary in summaries:
            writer.writerow(
                [
                    summary.run_timestamp,
                    summary.market_count,
                    summary.buy_yes_count,
                    summary.hold_count,
                    summary.avoid_count,
                    summary.taker_count,
                    summary.maker_count,
                    summary.skip_count,
                    summary.best_market_id,
                    summary.best_market_type,
                    summary.best_net_edge,
                    summary.best_action,
                    summary.best_execution_mode,
                    summary.best_question,
                ]
            )
    return path


def print_paper_report_summary(summaries: list[PaperRunSummary]) -> None:
    if not summaries:
        print("paper_report | runs=0")
        return
    latest = summaries[-1]
    print(
        f"paper_report | runs={len(summaries)} | latest_markets={latest.market_count} | "
        f"latest_taker={latest.taker_count} | latest_maker={latest.maker_count} | "
        f"best_net_edge={latest.best_net_edge:.4f} | best_market={latest.best_market_id}"
    )


def write_data_quality_csv(stats: list[MarketHistoryStats], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "data_quality.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_id",
                "market_type",
                "yes_token_id",
                "price_point_count",
                "first_timestamp",
                "last_timestamp",
                "question",
            ]
        )
        for item in stats:
            writer.writerow(
                [
                    item.market_id,
                    item.market_type,
                    item.yes_token_id,
                    item.price_point_count,
                    item.first_timestamp,
                    item.last_timestamp,
                    item.question,
                ]
            )
    return path


def print_data_quality_summary(stats: list[MarketHistoryStats]) -> None:
    markets = len(stats)
    covered = len([item for item in stats if item.price_point_count > 0])
    tradable_sample = len([item for item in stats if item.price_point_count >= 24])
    total_points = sum(item.price_point_count for item in stats)
    print(
        f"data_quality | markets={markets} | with_history={covered} | "
        f"with_24plus_points={tradable_sample} | price_points={total_points}"
    )


def _write_portfolio_points(path: Path, points: list[PortfolioPoint]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "timestamp",
                "market_id",
                "action",
                "cash",
                "invested",
                "equity",
                "peak_equity",
                "drawdown",
                "pnl",
                "fee",
                "slippage",
            ]
        )
        for point in points:
            writer.writerow(
                [
                    point.timestamp,
                    point.market_id,
                    point.action,
                    point.cash,
                    point.invested,
                    point.equity,
                    point.peak_equity,
                    point.drawdown,
                    point.pnl,
                    point.fee,
                    point.slippage,
                ]
            )


def _write_portfolio_summary(path: Path, summary: PortfolioSummary) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "starting_cash",
                "ending_equity",
                "realized_pnl",
                "total_fees",
                "total_slippage",
                "max_drawdown",
                "event_count",
            ]
        )
        writer.writerow(
            [
                summary.starting_cash,
                summary.ending_equity,
                summary.realized_pnl,
                summary.total_fees,
                summary.total_slippage,
                summary.max_drawdown,
                summary.event_count,
            ]
        )
