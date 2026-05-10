from __future__ import annotations

import argparse
import sys

from .backtest import backtest_market
from .cache import CachePolicy, JsonCache
from .classifier import MARKET_TYPES, is_market_type
from .clob import get_price_history
from .config import load_config
from .http import HttpError
from .portfolio import build_portfolio_curve, summarize_portfolio
from .polymarket import discover_btc_markets
from .reporting import (
    print_aggregate_summary,
    print_market_table,
    print_portfolio_summary,
    print_signal,
    write_aggregate_summary_csv,
    write_all_order_events_csv,
    write_backtest_csv,
    write_order_events_csv,
    write_portfolio_curve_csv,
    write_portfolio_summary_csv,
    write_summary_csv,
)
from .signals import build_signal
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
    subparsers.add_parser("cache-info", help="show local HTTP cache status")
    subparsers.add_parser("explain-risk", help="explain the current risk limits")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "discover":
        print_market_table(_filter_markets(discover_btc_markets(config), args.market_type))
    elif args.command == "signals":
        for market in _filter_markets(discover_btc_markets(config), args.market_type):
            history = _safe_history(config, market)
            if not history:
                continue
            print_signal(market, build_signal(market, history, config.signal, config.backtest))
    elif args.command == "backtest":
        results = []
        summaries = []
        for market in _filter_markets(discover_btc_markets(config), args.market_type):
            history = _safe_history(config, market)
            if not history:
                continue
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
            print_portfolio_summary(portfolio_summary)
            print(f"orders_csv={orders_path}")
            print(f"portfolio_curve_csv={curve_path}")
            print(f"portfolio_summary_csv={portfolio_summary_path}")
    elif args.command == "explain-risk":
        _explain_risk(config)
    elif args.command == "cache-info":
        _print_cache_info(config)


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


def _safe_history(config, market):
    try:
        return get_price_history(config, market.yes_token_id or "")
    except HttpError as exc:
        print(f"warning: skip {market.id} history: {exc}", file=sys.stderr)
        return []


def _filter_markets(markets, market_type):
    return [market for market in markets if is_market_type(market, market_type)]


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


if __name__ == "__main__":
    main()
