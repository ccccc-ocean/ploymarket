from __future__ import annotations

import argparse
import sys
from time import sleep, time

from .backtest import backtest_market
from .cache import CachePolicy, JsonCache
from .classifier import MARKET_TYPES, is_market_type
from .clob import get_price_history
from .config import load_config
from .execution import plan_execution
from .http import HttpError
from .portfolio import build_mark_to_market_curve, build_portfolio_curve, summarize_portfolio
from .paper import build_paper_signal_row, summarize_paper_rows
from .paper_report import load_paper_run_summaries
from .polymarket import discover_btc_markets
from .reporting import (
    print_aggregate_summary,
    print_market_table,
    print_portfolio_summary,
    print_paper_report_summary,
    print_data_quality_summary,
    print_signal,
    write_aggregate_summary_csv,
    write_all_order_events_csv,
    write_backtest_csv,
    write_mark_to_market_curve_csv,
    write_mark_to_market_summary_csv,
    write_order_events_csv,
    write_portfolio_curve_csv,
    write_portfolio_summary_csv,
    write_paper_signal_rows_csv,
    write_paper_report_csv,
    write_data_quality_csv,
    write_summary_csv,
)
from .signals import build_signal
from .storage import storage_from_config
from .summary import aggregate_summaries, summarize_all, summarize_market


DEFAULT_CONFIG = "config/default.toml"


def main() -> None:
    parser = argparse.ArgumentParser(description="BTC prediction-market research simulator")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="find active BTC-related prediction markets")
    discover_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    signals_parser = subparsers.add_parser("signals", help="print current signals for discovered markets")
    signals_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    backtest_parser = subparsers.add_parser("backtest", help="run a simple historical paper-trading backtest")
    backtest_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    replay_parser = subparsers.add_parser("replay-backtest", help="run a backtest using only local SQLite data")
    replay_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="price_target")
    paper_parser = subparsers.add_parser("paper-run", help="run one paper-trading signal scan")
    paper_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="price_target")
    paper_loop_parser = subparsers.add_parser("paper-loop", help="run repeated paper-trading signal scans")
    paper_loop_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="price_target")
    paper_loop_parser.add_argument("--interval-seconds", type=int, default=300)
    paper_loop_parser.add_argument("--iterations", type=int, default=1, help="0 means run until interrupted")
    subparsers.add_parser("paper-report", help="summarize saved paper-run outputs")
    subparsers.add_parser("cache-info", help="show local HTTP cache status")
    subparsers.add_parser("storage-info", help="show local SQLite storage status")
    subparsers.add_parser("data-quality", help="summarize local SQLite market/history coverage")
    subparsers.add_parser("explain-risk", help="explain the current risk limits")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "discover":
        markets = _filter_markets(discover_btc_markets(config), args.market_type)
        storage_from_config(config).save_markets(markets)
        print_market_table(markets)
    elif args.command == "signals":
        markets = _filter_markets(discover_btc_markets(config), args.market_type)
        storage = storage_from_config(config)
        storage.save_markets(markets)
        for market in markets:
            history = _safe_history(config, market, storage)
            if not history:
                continue
            storage.save_price_history(market.yes_token_id or "", history)
            print_signal(market, build_signal(market, history, config.signal, config.backtest))
    elif args.command == "backtest":
        storage = storage_from_config(config)
        markets = _filter_markets(discover_btc_markets(config), args.market_type)
        storage.save_markets(markets)
        _run_backtest(config, markets, storage, prefer_local=False)
    elif args.command == "replay-backtest":
        storage = storage_from_config(config)
        markets = _filter_markets(storage.load_markets(), args.market_type)
        if not markets:
            raise SystemExit("No local markets found. Run discover or paper-run first.")
        _run_backtest(config, markets, storage, prefer_local=True)
    elif args.command == "paper-run":
        _run_paper_scan(config, args.market_type)
    elif args.command == "paper-loop":
        _run_paper_loop(config, args.market_type, args.interval_seconds, args.iterations)
    elif args.command == "paper-report":
        _run_paper_report(config)
    elif args.command == "explain-risk":
        _explain_risk(config)
    elif args.command == "cache-info":
        _print_cache_info(config)
    elif args.command == "storage-info":
        _print_storage_info(config)
    elif args.command == "data-quality":
        _run_data_quality(config)


def _run_backtest(config, markets, storage, prefer_local: bool) -> None:
    results = []
    histories_by_market = {}
    summaries = []
    for market in markets:
        history = _safe_history(config, market, storage, prefer_local=prefer_local)
        if not history:
            continue
        histories_by_market[market.id] = history
        storage.save_price_history(market.yes_token_id or "", history)
        result = backtest_market(market, history, config)
        results.append(result)
        path = write_backtest_csv(result, config.backtest.output_dir)
        write_order_events_csv(result, config.backtest.output_dir)
        summary = summarize_market(market, result)
        summaries.append(summary)
        trade_count = len([trade for trade in result.trades if trade.action != "REJECTED"])
        total_fees = sum(trade.fee for trade in result.trades)
        total_slippage = sum(trade.slippage for trade in result.trades)
        print(
            f"{market.id} | trades={trade_count} | pnl={result.realized_pnl:.2f} | "
            f"fees={total_fees:.2f} | slippage={total_slippage:.2f} | ending_cash={result.ending_cash:.2f} | {path}"
        )
    if summaries:
        summary_path = write_summary_csv(summaries, config.backtest.output_dir)
        aggregate_summaries_by_type = aggregate_summaries(summaries)
        aggregate_path = write_aggregate_summary_csv([summarize_all(summaries)] + aggregate_summaries_by_type, config.backtest.output_dir)
        print_aggregate_summary(summarize_all(summaries))
        for aggregate in aggregate_summaries_by_type:
            print_aggregate_summary(aggregate)
        print(f"summary_csv={summary_path}")
        print(f"summary_by_type_csv={aggregate_path}")
    if results:
        orders_path = write_all_order_events_csv(results, config.backtest.output_dir)
        portfolio_curve = build_portfolio_curve(results, config)
        portfolio_summary = summarize_portfolio(portfolio_curve, config)
        curve_path = write_portfolio_curve_csv(portfolio_curve, config.backtest.output_dir)
        portfolio_summary_path = write_portfolio_summary_csv(portfolio_summary, config.backtest.output_dir)
        mtm_curve = build_mark_to_market_curve(results, histories_by_market, config)
        mtm_summary = summarize_portfolio(mtm_curve, config)
        mtm_curve_path = write_mark_to_market_curve_csv(mtm_curve, config.backtest.output_dir)
        mtm_summary_path = write_mark_to_market_summary_csv(mtm_summary, config.backtest.output_dir)
        print_portfolio_summary(portfolio_summary)
        print(f"mark_to_market | ending_equity={mtm_summary.ending_equity:.2f} | pnl={mtm_summary.realized_pnl:.2f} | max_drawdown={mtm_summary.max_drawdown:.1%} | events={mtm_summary.event_count}")
        print(f"orders_csv={orders_path}")
        print(f"portfolio_curve_csv={curve_path}")
        print(f"portfolio_summary_csv={portfolio_summary_path}")
        print(f"portfolio_mtm_curve_csv={mtm_curve_path}")
        print(f"portfolio_mtm_summary_csv={mtm_summary_path}")


def _explain_risk(config) -> None:
    risk = config.risk
    print("current paper-trading risk limits")
    print(f"- starting_cash: {risk.starting_cash:.2f} USDC")
    print(f"- max_position_usdc: 单笔最多 {risk.max_position_usdc:.2f} USDC")
    print(f"- max_market_exposure_usdc: 单个市场最多 {risk.max_market_exposure_usdc:.2f} USDC")
    print(f"- max_total_exposure_usdc: 所有持仓合计最多 {risk.max_total_exposure_usdc:.2f} USDC")
    print(f"- max_open_positions: 最多同时持有 {risk.max_open_positions} 个仓位")
    print(f"- daily_loss_limit_usdc: 单日已实现亏损达到 {risk.daily_loss_limit_usdc:.2f} USDC 后停止开仓")
    print(f"- max_drawdown_pct: 账户回撤达到 {risk.max_drawdown_pct:.0%} 后停止开仓")
    print(f"- stop_loss_pct: 单笔浮亏达到 {risk.stop_loss_pct:.0%} 后退出")
    print(f"- take_profit_pct: 单笔浮盈达到 {risk.take_profit_pct:.0%} 后退出")
    print(f"- max_spread: 买卖价差高于 {risk.max_spread:.2f} 不交易")


def _safe_history(config, market, storage=None, prefer_local: bool = False):
    token_id = market.yes_token_id or ""
    if prefer_local and storage is not None:
        local_history = storage.load_price_history(token_id)
        if local_history:
            return local_history
    try:
        history = get_price_history(config, token_id)
        return history
    except HttpError as exc:
        print(f"warning: skip {market.id} history: {exc}", file=sys.stderr)
        if storage is not None:
            local_history = storage.load_price_history(token_id)
            if local_history:
                print(f"warning: using local SQLite history for {market.id}", file=sys.stderr)
                return local_history
        return []


def _filter_markets(markets, market_type):
    return [market for market in markets if is_market_type(market, market_type)]


def _run_paper_scan(config, market_type: str) -> None:
    run_timestamp = int(time())
    storage = storage_from_config(config)
    markets = _filter_markets(_paper_markets(config, storage), market_type)
    rows = []
    for market in markets:
        history = _safe_history(config, market, storage, prefer_local=True)
        if not history:
            continue
        storage.save_price_history(market.yes_token_id or "", history)
        signal = build_signal(market, history, config.signal, config.backtest)
        execution_plan = plan_execution(market, signal, config.signal, config.backtest, config.execution)
        rows.append(build_paper_signal_row(market, signal, config.backtest.taker_fee_rate, run_timestamp, execution_plan))
    path = write_paper_signal_rows_csv(rows, config.backtest.output_dir, run_timestamp)
    summary = summarize_paper_rows(rows)
    print(
        f"paper_run | markets={summary['markets']} | buy_yes={summary['buy_yes']} | "
        f"hold={summary['hold']} | avoid={summary['avoid']} | taker={summary['taker']} | "
        f"maker={summary['maker']} | skip={summary['skip']} | {path}"
    )


def _paper_markets(config, storage):
    local_markets = storage.load_markets()
    if local_markets:
        return local_markets
    markets = discover_btc_markets(config)
    storage.save_markets(markets)
    return markets


def _run_paper_loop(config, market_type: str, interval_seconds: int, iterations: int) -> None:
    if interval_seconds < 0:
        raise SystemExit("--interval-seconds must be >= 0")
    if iterations < 0:
        raise SystemExit("--iterations must be >= 0")

    completed = 0
    while iterations == 0 or completed < iterations:
        completed += 1
        print(f"paper_loop | iteration={completed}")
        _run_paper_scan(config, market_type)
        if iterations != 0 and completed >= iterations:
            break
        sleep(interval_seconds)


def _run_paper_report(config) -> None:
    summaries = load_paper_run_summaries(config.backtest.output_dir)
    path = write_paper_report_csv(summaries, config.backtest.output_dir)
    print_paper_report_summary(summaries)
    print(f"paper_report_csv={path}")


def _print_cache_info(config) -> None:
    cache = JsonCache(
        CachePolicy(
            enabled=config.cache.enabled,
            directory=config.cache.directory,
            ttl_seconds=config.cache.ttl_seconds,
            stale_if_error=config.cache.stale_if_error,
        )
    )
    stats = cache.stats()
    print("local HTTP cache")
    print(f"- enabled: {stats.enabled}")
    print(f"- directory: {stats.directory}")
    print(f"- ttl_seconds: {config.cache.ttl_seconds}")
    print(f"- stale_if_error: {config.cache.stale_if_error}")
    print(f"- files: {stats.file_count}")
    print(f"- size_bytes: {stats.total_bytes}")


def _print_storage_info(config) -> None:
    stats = storage_from_config(config).stats()
    print("local SQLite storage")
    print(f"- enabled: {stats.enabled}")
    print(f"- sqlite_path: {stats.sqlite_path}")
    print(f"- markets: {stats.market_count}")
    print(f"- price_points: {stats.price_point_count}")


def _run_data_quality(config) -> None:
    stats = storage_from_config(config).market_history_stats()
    print_data_quality_summary(stats)
    path = write_data_quality_csv(stats, config.backtest.output_dir)
    print(f"data_quality_csv={path}")


if __name__ == "__main__":
    main()
