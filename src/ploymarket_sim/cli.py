from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import sleep, time

from .alignment import build_alignment_rows, summarize_alignment
from .backtest import backtest_market
from .blocked_edge_report import build_blocked_edge_report, print_blocked_edge_report, write_blocked_edge_report_csv
from .btc_regime import blocks_directional_entry
from .btc_price import get_btc_candles, load_btc_candles_csv, merge_btc_candles
from .cache import CachePolicy, JsonCache
from .classifier import MARKET_TYPES, classify_market, is_market_type, is_target_like_market_type
from .clob import get_price_history, get_token_quote
from .config import load_config
from .costs import estimate_entry_cost, fee_amount, taker_fee_rate
from .daily_report import build_daily_report, write_daily_report_csv
from .edge_report import build_edge_buckets_from_csv
from .execution import plan_execution
from .execution_stress import (
    build_execution_stress_rows,
    build_shadow_order_events,
    load_execution_stress_history,
    summarize_execution_stress,
    summarize_execution_stress_history,
    write_execution_stress_csv,
    write_execution_stress_report_csv,
    write_shadow_order_events_csv,
)
from .flow_scan import print_flow_scan_summary, scan_market_flows, write_flow_scan_csv
from .filter_reason_report import build_filter_reason_report, print_filter_reason_report, write_filter_reason_report_csv
from .http import HttpError
from .live_universe_report import build_live_universe_report, print_live_universe_report, write_live_universe_report_csv
from .market_rules import blocks_btc_strike_entry, blocks_price_range_entry, blocks_price_target_entry, extract_usd_strike, infer_strike_direction, latest_btc_candle_at_or_before
from .market_type_report import build_market_type_report, print_market_type_report, write_market_type_report_csv
from .observation_report import build_observation_report, print_observation_report, write_observation_report_csv
from .open_position_report import build_open_position_report, print_open_position_report, write_open_position_report_csv
from .portfolio import build_mark_to_market_curve, build_portfolio_curve, summarize_portfolio
from .paper import build_paper_signal_row, summarize_paper_rows
from .paper_report import load_paper_run_summaries
from .paper_sample_report import build_paper_sample_report, print_paper_sample_report, write_paper_sample_report_csv
from .probe_performance_report import build_probe_performance_report, print_probe_performance_report, probe_family_from_reason, write_probe_performance_report_csv
from .polymarket import discover_btc_markets, get_market_by_id
from .reporting import (
    print_aggregate_summary,
    print_market_table,
    print_portfolio_summary,
    print_paper_report_summary,
    print_data_quality_summary,
    print_alignment_summary,
    print_edge_report_summary,
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
    write_btc_candles_csv,
    write_alignment_rows_csv,
    write_alignment_summary_csv,
    write_data_quality_csv,
    write_edge_report_csv,
    write_summary_csv,
)
from .reversal_backtest import (
    default_reversal_strategies,
    print_reversal_summary,
    run_reversal_backtest,
    summarize_reversal_results,
    write_reversal_summary_csv,
    write_reversal_trades_csv,
)
from .signals import Signal, build_signal
from .side_diagnostics import build_side_diagnostics, print_side_diagnostics, write_side_diagnostics_csv
from .spread_scan import print_spread_scan_summary, scan_spreads, write_spread_scan_csv
from .storage import PaperPositionState, storage_from_config
from .strategy_autotune_report import (
    AutotuneContext,
    build_strategy_autotune_report,
    print_strategy_autotune_report,
    write_strategy_autotune_report_csv,
)
from .strategy_review import build_strategy_review, print_strategy_review, write_strategy_review_csv
from .strategy_profiles import is_tradeable_market, strategy_config_for_market
from .strategy_sweep import print_strategy_sweep_summary, run_strategy_sweep, write_strategy_sweep_csv
from .strike_report import build_strike_report, print_strike_report, write_strike_report_csv
from .summary import aggregate_summaries, summarize_all, summarize_market
from .touch_below_path_report import build_touch_below_path_report, print_touch_below_path_report, write_touch_below_path_report_csv


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
    replay_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    paper_parser = subparsers.add_parser("paper-run", help="run one paper-trading signal scan")
    paper_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    paper_loop_parser = subparsers.add_parser("paper-loop", help="run repeated paper-trading signal scans")
    paper_loop_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    paper_loop_parser.add_argument("--interval-seconds", type=int, default=300)
    paper_loop_parser.add_argument("--iterations", type=int, default=1, help="0 means run until interrupted")
    subparsers.add_parser("paper-report", help="summarize saved paper-run outputs")
    subparsers.add_parser("cache-info", help="show local HTTP cache status")
    subparsers.add_parser("storage-info", help="show local SQLite storage status")
    subparsers.add_parser("data-quality", help="summarize local SQLite market/history coverage")
    subparsers.add_parser("btc-price", help="fetch external BTC spot candles")
    alignment_parser = subparsers.add_parser("alignment-report", help="align local Polymarket YES history with BTC candles")
    alignment_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    alignment_parser.add_argument("--max-points-per-market", type=int, default=None)
    edge_parser = subparsers.add_parser("edge-report", help="bucket alignment rows to inspect conditional edge")
    edge_parser.add_argument("--min-samples", type=int, default=30)
    sweep_parser = subparsers.add_parser("strategy-sweep", help="try conservative 5-minute strategy parameter candidates")
    sweep_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    sweep_parser.add_argument("--limit", type=int, default=10)
    sweep_parser.add_argument("--candidate-limit", type=int, default=None)
    sweep_parser.add_argument("--max-points-per-market", type=int, default=None)
    spread_parser = subparsers.add_parser("spread-scan", help="scan live YES/NO order books for complete-set spread edges")
    spread_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    reversal_parser = subparsers.add_parser("reversal-backtest", help="compare BUY_YES, BUY_NO, reversal, and stop-loss variants")
    reversal_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="above_below_expiry")
    flow_parser = subparsers.add_parser("flow-scan", help="scan recent Polymarket trade flow and large-wallet pressure")
    flow_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    flow_parser.add_argument("--limit", type=int, default=250)
    flow_parser.add_argument("--large-trade-usdc", type=float, default=500.0)
    subparsers.add_parser("market-type-report", help="compare local backtest results by BTC market type")
    observation_parser = subparsers.add_parser("observation-report", help="score observed market types for possible promotion")
    observation_parser.add_argument("--recent-runs", type=int, default=288)
    sample_parser = subparsers.add_parser("paper-sample-report", help="summarize recent paper-run sample density and probe activity")
    sample_parser.add_argument("--recent-runs", type=int, default=288)
    live_universe_parser = subparsers.add_parser("live-universe-report", help="compare live BTC market coverage with recent paper samples")
    live_universe_parser.add_argument("--recent-runs", type=int, default=288)
    review_parser = subparsers.add_parser("strategy-review", help="review whether paper trading is sample-starved or over-filtered")
    review_parser.add_argument("--recent-runs", type=int, default=288)
    filter_parser = subparsers.add_parser("filter-reason-report", help="summarize why recent paper-run candidates were skipped")
    filter_parser.add_argument("--recent-runs", type=int, default=288)
    blocked_edge_parser = subparsers.add_parser("blocked-edge-report", help="summarize positive-edge skips by market and later taker status")
    blocked_edge_parser.add_argument("--recent-runs", type=int, default=288)
    touch_below_path_parser = subparsers.add_parser("touch-below-path-report", help="classify touch_below path state for safer sample expansion")
    touch_below_path_parser.add_argument("--recent-runs", type=int, default=288)
    subparsers.add_parser("probe-performance-report", help="summarize realized PnL by paper probe family")
    autotune_parser = subparsers.add_parser("strategy-autotune-report", help="turn strategy/probe diagnostics into prioritized next actions")
    autotune_parser.add_argument("--recent-runs", type=int, default=288)
    open_position_parser = subparsers.add_parser("open-position-report", help="summarize current open paper positions")
    open_position_parser.add_argument("--live-quotes", action="store_true", help="fetch live CLOB bids for current-side PnL")
    subparsers.add_parser("side-diagnostics", help="break replay PnL down by market type and YES/NO side")
    subparsers.add_parser("strike-report", help="summarize BTC daily range backtest results by strike")
    subparsers.add_parser("daily-report", help="summarize paper, replay, alignment, and edge outputs")
    subparsers.add_parser("explain-risk", help="explain the current risk limits")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "discover":
        storage = storage_from_config(config)
        markets = _filter_markets(_discover_markets_with_quality_guard(config, storage, "discover"), args.market_type)
        print_market_table(markets)
    elif args.command == "signals":
        storage = storage_from_config(config)
        markets = _filter_markets(_discover_markets_with_quality_guard(config, storage, "signals"), args.market_type)
        for market in markets:
            history = _safe_history(config, market, storage)
            if not history:
                continue
            storage.save_price_history(market.yes_token_id or "", history)
            market_config = strategy_config_for_market(config, market)
            print_signal(market, build_signal(market, history, market_config.signal, market_config.backtest))
    elif args.command == "backtest":
        storage = storage_from_config(config)
        markets = _filter_markets(_discover_markets_with_quality_guard(config, storage, "backtest"), args.market_type)
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
    elif args.command == "btc-price":
        _run_btc_price(config)
    elif args.command == "alignment-report":
        _run_alignment_report(config, args.market_type, args.max_points_per_market)
    elif args.command == "edge-report":
        _run_edge_report(config, args.min_samples)
    elif args.command == "strategy-sweep":
        _run_strategy_sweep(config, args.market_type, args.limit, args.candidate_limit, args.max_points_per_market)
    elif args.command == "spread-scan":
        _run_spread_scan(config, args.market_type)
    elif args.command == "reversal-backtest":
        _run_reversal_backtest(config, args.market_type)
    elif args.command == "flow-scan":
        _run_flow_scan(config, args.market_type, args.limit, args.large_trade_usdc)
    elif args.command == "market-type-report":
        _run_market_type_report(config)
    elif args.command == "observation-report":
        _run_observation_report(config, args.recent_runs)
    elif args.command == "paper-sample-report":
        _run_paper_sample_report(config, args.recent_runs)
    elif args.command == "live-universe-report":
        _run_live_universe_report(config, args.recent_runs)
    elif args.command == "strategy-review":
        _run_strategy_review(config, args.recent_runs)
    elif args.command == "filter-reason-report":
        _run_filter_reason_report(config, args.recent_runs)
    elif args.command == "blocked-edge-report":
        _run_blocked_edge_report(config, args.recent_runs)
    elif args.command == "touch-below-path-report":
        _run_touch_below_path_report(config, args.recent_runs)
    elif args.command == "probe-performance-report":
        _run_probe_performance_report(config)
    elif args.command == "strategy-autotune-report":
        _run_strategy_autotune_report(config, args.recent_runs)
    elif args.command == "open-position-report":
        _run_open_position_report(config, args.live_quotes)
    elif args.command == "side-diagnostics":
        _run_side_diagnostics(config)
    elif args.command == "strike-report":
        _run_strike_report(config)
    elif args.command == "daily-report":
        _run_daily_report(config)


def _run_backtest(config, markets, storage, prefer_local: bool) -> None:
    results = []
    histories_by_market = {}
    summaries = []
    btc_candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    for market in markets:
        history = _safe_history(config, market, storage, prefer_local=prefer_local, use_cache=prefer_local)
        if not history:
            continue
        histories_by_market[market.id] = history
        storage.save_price_history(market.yes_token_id or "", history)
        result = backtest_market(market, history, config, btc_candles)
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
    print(f"- take_profit_pct: 回测/策略单笔浮盈达到 {risk.take_profit_pct:.0%} 后退出")
    print(f"- paper_full_take_profit_pct: 模拟盘单笔浮盈达到 {risk.paper_full_take_profit_pct:.0%} 后全量止盈")
    print(f"- partial_take_profit_pct: 单笔浮盈达到 {risk.partial_take_profit_pct:.1%} 后先卖出 {risk.partial_take_profit_fraction:.0%}")
    print(f"- trailing_stop: 浮盈达到 {risk.trailing_stop_activation_pct:.0%} 后，如果从峰值回吐 {risk.trailing_stop_drawdown_pct:.0%} 则保护性退出")
    print(f"- paper_take_profit_reentry_cooldown_seconds: 止盈后同市场短冷却 {risk.paper_take_profit_reentry_cooldown_seconds} 秒")
    print(f"- paper_reentry_edge_multiplier: 止盈后重新入场需要达到普通 edge 门槛的 {risk.paper_reentry_edge_multiplier:.1f} 倍")
    print(f"- max_spread: 买卖价差高于 {risk.max_spread:.2f} 不交易")


def _safe_history(config, market, storage=None, prefer_local: bool = False, use_cache: bool = True, allow_local_fallback: bool = True):
    token_id = market.yes_token_id or ""
    if prefer_local and storage is not None:
        local_history = storage.load_price_history(token_id)
        if local_history:
            return local_history
    try:
        history = get_price_history(config, token_id, use_cache=use_cache)
        return history
    except HttpError as exc:
        print(f"warning: skip {market.id} history: {exc}", file=sys.stderr)
        if storage is not None and allow_local_fallback:
            local_history = storage.load_price_history(token_id)
            if local_history:
                print(f"warning: using local SQLite history for {market.id}", file=sys.stderr)
                return local_history
        return []


def _filter_markets(markets, market_type):
    return [market for market in markets if is_market_type(market, market_type)]


def _discover_markets_with_quality_guard(config, storage, purpose: str):
    local_markets = storage.load_markets()
    try:
        live_markets = discover_btc_markets(config, use_cache=False)
    except Exception as exc:
        print(f"warning: live market discovery failed for {purpose}: {exc}", file=sys.stderr)
        live_markets = []

    if _market_discovery_is_healthy(live_markets, local_markets):
        storage.save_markets(live_markets)
        return live_markets

    print(
        f"warning: live market discovery degraded for {purpose}: "
        f"live={len(live_markets)} local={len(local_markets)}",
        file=sys.stderr,
    )
    try:
        cached_markets = discover_btc_markets(config, use_cache=True)
    except Exception as exc:
        print(f"warning: cached market discovery failed for {purpose}: {exc}", file=sys.stderr)
        cached_markets = []

    if len(cached_markets) > max(len(live_markets), len(local_markets)):
        print(f"warning: using HTTP cached markets for {purpose}: cached={len(cached_markets)}", file=sys.stderr)
        storage.save_markets(cached_markets)
        return cached_markets

    if local_markets:
        print(f"warning: using local SQLite markets for {purpose}: local={len(local_markets)}", file=sys.stderr)
        return local_markets

    return live_markets


def _discover_live_markets_or_empty(config, storage, purpose: str):
    local_markets = storage.load_markets()
    try:
        live_markets = discover_btc_markets(config, use_cache=False)
    except Exception as exc:
        print(f"warning: live market discovery failed for {purpose}: {exc}", file=sys.stderr)
        live_markets = []
    if _realtime_market_discovery_is_healthy(live_markets):
        storage.save_markets(live_markets)
        return live_markets
    if live_markets:
        storage.save_markets(live_markets)
    print(
        f"warning: live market discovery degraded for {purpose}; not using stale local/cache for realtime decisions: "
        f"live={len(live_markets)} local={len(local_markets)}",
        file=sys.stderr,
    )
    fresh_markets = _fresh_live_markets(config, storage)
    if fresh_markets:
        print(
            f"warning: using fresh live-observed markets for {purpose}: "
            f"fresh={len(fresh_markets)} ttl_seconds={config.storage.fresh_market_ttl_seconds}",
            file=sys.stderr,
        )
        return fresh_markets
    return []


def _market_discovery_is_healthy(live_markets, local_markets) -> bool:
    if len(live_markets) >= 10:
        return not local_markets or len(live_markets) >= len(local_markets) * 0.5
    return bool(live_markets) and not local_markets


def _realtime_market_discovery_is_healthy(live_markets) -> bool:
    # The local store accumulates expired/research markets and is not a valid
    # coverage baseline for current live-only trading decisions.
    return len(live_markets) >= 10


def _fresh_live_markets(config, storage):
    ttl_seconds = max(0, int(config.storage.fresh_market_ttl_seconds))
    if ttl_seconds <= 0:
        return []
    return storage.load_markets_observed_after(time() - ttl_seconds)


def _run_paper_scan(config, market_type: str) -> None:
    run_timestamp = int(time())
    storage = storage_from_config(config)
    live_markets = _filter_markets(_paper_markets(config, storage), market_type)
    markets = _paper_markets_including_open_positions(storage, live_markets, market_type)
    btc_candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    btc_candles = _fresh_paper_btc_candles(config, btc_candles, run_timestamp)
    rows = []
    stress_candidates = []
    probe_candidates = []
    probe_slots = _paper_probe_available_slots(config, storage)
    disabled_probe_families = _underperforming_probe_families(config, storage)
    for market in markets:
        history = _safe_history(config, market, storage, prefer_local=False, use_cache=False, allow_local_fallback=False)
        if not history:
            continue
        storage.save_price_history(market.yes_token_id or "", history)
        market_config = strategy_config_for_market(config, market)
        state_signal = _paper_position_signal_with_live_quote(
            config, storage, market, history[-1].price, run_timestamp, disabled_probe_families
        )
        if state_signal is not None:
            execution_plan = plan_execution(market, state_signal, market_config.signal, market_config.backtest, market_config.execution, history[-1].price)
            rows.append(build_paper_signal_row(market, state_signal, config.backtest.taker_fee_rate, run_timestamp, execution_plan))
            continue
        if not is_tradeable_market(market):
            signal = build_signal(market, history, market_config.signal, market_config.backtest)
            signal = Signal("HOLD", 0.0, signal.edge, signal.net_edge, "当前市场类型暂不交易，只记录观察")
        else:
            signal = build_signal(market, history, market_config.signal, market_config.backtest)
            blocked, reason = blocks_btc_strike_entry(
                market,
                history[-1].timestamp,
                btc_candles,
                signal.action,
            )
            if blocked:
                signal = Signal("HOLD", 0.0, signal.edge, signal.net_edge, reason)
            blocked, reason = blocks_price_range_entry(
                market,
                signal.action,
                history[-1].timestamp,
                btc_candles,
                history[-1].price,
                config.risk.range_buy_yes_max_price,
                config.risk.range_buy_no_max_price,
                config.risk.range_market_safety_band_pct,
                config.risk.btc_moving_away_return_pct,
            )
            if blocked:
                signal = Signal("HOLD", 0.0, signal.edge, signal.net_edge, reason)
            blocked, reason = blocks_price_target_entry(
                market,
                signal.action,
                history[-1].timestamp,
                btc_candles,
                config.risk.target_market_max_distance_pct,
                history[-1].price,
                config.risk.target_buy_yes_max_price,
                config.risk.target_buy_no_max_price,
                config.risk.btc_moving_away_return_pct,
            )
            if blocked:
                signal = Signal("HOLD", 0.0, signal.edge, signal.net_edge, reason)
            blocked, reason = blocks_directional_entry(market, signal, btc_candles, history[-1].timestamp)
            if blocked:
                signal = Signal("HOLD", 0.0, signal.edge, signal.net_edge, reason)
            blocked, reason = _strategy_loss_pause_blocks_entry(config, storage, market, signal.action, history[-1].timestamp)
            if blocked:
                signal = Signal("HOLD", 0.0, signal.edge, signal.net_edge, reason)
        signal, execution_plan = _live_paper_entry_plan(config, market, signal, market_config, history[-1].price)
        if execution_plan.mode == "TAKER" and _paper_reentry_edge_too_weak(
            config,
            storage,
            market,
            execution_plan.expected_net_edge,
            market_config.signal.min_edge,
        ):
            signal = Signal("HOLD", 0.0, signal.edge, signal.net_edge, "止盈后重新入场 edge 不够强，避免频繁止盈/再开仓消耗手续费")
            execution_plan = plan_execution(market, signal, market_config.signal, market_config.backtest, market_config.execution, history[-1].price)
        if execution_plan.mode == "SKIP" and probe_slots > 0:
            probe_signal = _paper_probe_signal(config, market, history, market_config, signal, btc_candles, disabled_probe_families)
            if probe_signal is not None:
                probe_signal, probe_plan = _live_paper_entry_plan(config, market, probe_signal, market_config, history[-1].price)
                if probe_plan.mode == "TAKER":
                    probe_candidates.append((probe_plan.expected_net_edge, len(rows), market, probe_signal, probe_plan))
        if execution_plan.mode == "TAKER":
            stress_candidate = build_paper_signal_row(
                market, signal, config.backtest.taker_fee_rate, run_timestamp, execution_plan
            )
            stress_candidates.append(stress_candidate)
        if execution_plan.mode == "TAKER":
            _save_paper_position(config, storage, market, execution_plan, run_timestamp)
        rows.append(build_paper_signal_row(market, signal, config.backtest.taker_fee_rate, run_timestamp, execution_plan))
    if probe_candidates and probe_slots > 0:
        max_new_probes = max(1, int(config.risk.paper_probe_max_new_positions_per_run))
        remaining_new_probes = max(0, max_new_probes - len(stress_candidates))
        if remaining_new_probes <= 0:
            remaining_new_probes = 1 if not stress_candidates else 0
        for _, row_index, market, probe_signal, probe_plan in sorted(probe_candidates, key=lambda item: item[0], reverse=True)[
            : min(probe_slots, remaining_new_probes)
        ]:
            _save_paper_position(config, storage, market, probe_plan, run_timestamp, _paper_probe_trade_size_usdc(config, probe_signal))
            probe_row = build_paper_signal_row(market, probe_signal, config.backtest.taker_fee_rate, run_timestamp, probe_plan)
            rows[row_index] = probe_row
            stress_candidates.append(probe_row)
    storage.save_paper_snapshots(rows)
    path = write_paper_signal_rows_csv(rows, config.backtest.output_dir, run_timestamp)
    summary = summarize_paper_rows(rows)
    print(
        f"paper_run | markets={summary['markets']} | buy_yes={summary['buy_yes']} | "
        f"buy_no={summary['buy_no']} | "
        f"hold={summary['hold']} | avoid={summary['avoid']} | taker={summary['taker']} | "
        f"maker={summary['maker']} | skip={summary['skip']} | {path}"
    )
    if config.execution_stress.enabled:
        stress_rows = build_execution_stress_rows(
            stress_candidates, config.execution_stress, config.backtest.trade_size_usdc
        )
        stress_path = write_execution_stress_csv(stress_rows, config.backtest.output_dir, run_timestamp)
        stress_summary = summarize_execution_stress(stress_rows)
        event_path = write_shadow_order_events_csv(
            build_shadow_order_events(stress_rows), config.backtest.output_dir, run_timestamp
        )
        stress_files = list(Path(config.backtest.output_dir).glob("execution_stress_[0-9]*.csv"))
        history = summarize_execution_stress_history(
            load_execution_stress_history(config.backtest.output_dir), observed_run_count=len(stress_files)
        )
        history_path = write_execution_stress_report_csv(history, config.backtest.output_dir)
        print(
            f"execution_stress | candidates={stress_summary.candidates} | scenarios={stress_summary.scenarios} | "
            f"robust={stress_summary.robust_candidates} | blocks={stress_summary.market_stress_blocks} | "
            f"partial_cancels={stress_summary.partial_fill_cancels} | no_fill={stress_summary.no_fill_scenarios} | "
            f"fail_safe={stress_summary.fail_safe_scenarios} | "
            f"{stress_path} | events={event_path}"
        )
        print(
            f"execution_stress_report | runs={history.runs} | candidates={history.candidates} | "
            f"robust={history.robust_candidates} | latency_blocked={history.latency_blocked_candidates} | "
            f"partial_cancels={history.partial_fill_cancels} | no_fill={history.no_fill_scenarios} | "
            f"fail_safe={history.fail_safe_scenarios} | "
            f"{history_path}"
        )
    if _paper_run_data_degraded(market_type, live_markets):
        raise SystemExit("paper-run realtime data degraded: no live market observations written")


def _paper_markets(config, storage):
    return _discover_live_markets_or_empty(config, storage, "paper-run")


def _paper_markets_including_open_positions(storage, live_markets, market_type: str):
    by_id = {market.id: market for market in live_markets}
    open_market_ids = storage.load_open_paper_market_ids()
    for market in _filter_markets(storage.load_markets(), market_type):
        if market.id in open_market_ids and market.id not in by_id:
            by_id[market.id] = market
    return list(by_id.values())


def _paper_run_data_degraded(market_type: str, live_markets: list) -> bool:
    # The unattended live cycle scans all markets; an empty all-market run
    # means market discovery failed even if stored open positions were checked.
    return market_type == "all" and not live_markets


def _fresh_paper_btc_candles(config, candles, run_timestamp: int):
    if not candles:
        return []
    max_age_seconds = max(15 * 60, config.signal.history_fidelity_minutes * 60 * 3)
    age_seconds = max(0, run_timestamp - candles[-1].timestamp)
    if age_seconds > max_age_seconds:
        print(
            f"warning: BTC spot context stale for paper-run: age_seconds={age_seconds} max_age_seconds={max_age_seconds}; blocking new directional entries",
            file=sys.stderr,
        )
        return []
    return candles


def _paper_position_signal_with_live_quote(
    config,
    storage,
    market,
    yes_price: float,
    run_timestamp: int,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    position = storage.load_paper_position(market.id)
    if position is None or position.status != "open":
        return _paper_position_state_signal(config, storage, market, yes_price, run_timestamp)
    if _paper_market_end_date_has_passed(market, run_timestamp):
        settlement_signal = _paper_settlement_signal(config, storage, market, position, run_timestamp)
        if settlement_signal is not None:
            return settlement_signal
    token_id = market.yes_token_id if position.side == "YES" else market.no_token_id
    if not token_id:
        return Signal("HOLD", 0.0, 0.0, 0.0, "已有模拟持仓，但缺少对应 token，无法用实时 bid 退出")
    try:
        quote = get_token_quote(config, token_id)
    except HttpError as exc:
        settlement_signal = _paper_settlement_signal(config, storage, market, position, run_timestamp)
        if settlement_signal is not None:
            return settlement_signal
        return Signal("HOLD", 0.0, 0.0, 0.0, f"已有模拟持仓，但实时 bid 获取失败，暂停退出判断: {exc}")
    if quote.bid is None:
        settlement_signal = _paper_settlement_signal(config, storage, market, position, run_timestamp)
        if settlement_signal is not None:
            return settlement_signal
        return Signal("HOLD", 0.0, 0.0, 0.0, "已有模拟持仓，但订单簿缺少实时 bid，暂停退出判断")
    disabled_probe_families = disabled_probe_families or set()
    probe_family = _paper_probe_family_for_position(config, position)
    if probe_family in disabled_probe_families:
        realized_pnl = _paper_close_value(position, quote.bid, market, config)
        storage.close_paper_position(market.id, run_timestamp, realized_pnl, run_timestamp + config.risk.paper_reentry_cooldown_seconds)
        return Signal(
            "HOLD",
            0.0,
            0.0,
            0.0,
            f"模拟探索仓家族已停用，按实时 bid risk-off 退出; family={probe_family}; bid={quote.bid:.3f}; realized_pnl={realized_pnl:.2f}",
        )
    return _paper_position_state_signal(config, storage, market, yes_price, run_timestamp, quote.bid)


def _paper_probe_available_slots(config, storage) -> int:
    if not config.risk.paper_probe_enabled:
        return 0
    zero_run_threshold = max(0, int(config.risk.paper_probe_zero_run_threshold))
    if zero_run_threshold > 0 and _recent_zero_taker_runs(config.backtest.output_dir) < zero_run_threshold:
        return 0
    soft_max_open = max(0, int(config.risk.paper_probe_max_open_positions))
    hard_max_open = max(soft_max_open, int(config.risk.paper_probe_hard_max_open_positions))
    open_count = len(_paper_open_probe_positions(config, storage))
    if open_count < soft_max_open:
        return soft_max_open - open_count
    if open_count >= hard_max_open:
        return 0
    open_exposure = _paper_open_probe_exposure_usdc(config, storage)
    next_trade_size = max(0.0, float(config.risk.paper_probe_trade_size_usdc))
    max_probe_exposure = max(0.0, float(config.risk.paper_probe_max_total_exposure_usdc))
    if max_probe_exposure <= 0 or open_exposure + next_trade_size > max_probe_exposure:
        return 0
    return hard_max_open - open_count


def _paper_open_probe_positions(config, storage) -> list[PaperPositionState]:
    probe_keys = _paper_probe_entry_keys(config.backtest.output_dir)
    positions = []
    for market_id in storage.load_open_paper_market_ids():
        position = storage.load_paper_position(market_id)
        if position is not None and position.status == "open" and (position.market_id, position.opened_at) in probe_keys:
            positions.append(position)
    return positions


def _paper_probe_entry_keys(output_dir: str) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    for path in sorted(Path(output_dir).glob("paper_run_*.csv")):
        with path.open("r", newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if row.get("execution_mode") != "TAKER":
                    continue
                reason = row.get("reason", "")
                if "探索仓" not in reason and "挑战仓" not in reason:
                    continue
                keys.add((row.get("market_id", ""), int(float(row.get("run_timestamp") or 0))))
    return keys


def _paper_probe_entry_families(output_dir: str) -> dict[tuple[str, int], str]:
    families: dict[tuple[str, int], str] = {}
    for path in sorted(Path(output_dir).glob("paper_run_*.csv")):
        with path.open("r", newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if row.get("execution_mode") != "TAKER":
                    continue
                reason = row.get("reason", "")
                if "探索仓" not in reason and "挑战仓" not in reason:
                    continue
                key = (row.get("market_id", ""), int(float(row.get("run_timestamp") or 0)))
                families[key] = probe_family_from_reason(reason)
    return families


def _paper_probe_family_for_position(config, position: PaperPositionState) -> str | None:
    return _paper_probe_entry_families(config.backtest.output_dir).get((position.market_id, position.opened_at))


def _paper_open_probe_exposure_usdc(config, storage) -> float:
    return sum(max(0.0, position.notional) for position in _paper_open_probe_positions(config, storage))


def _paper_open_exposure_usdc(storage) -> float:
    exposure = 0.0
    for market_id in storage.load_open_paper_market_ids():
        position = storage.load_paper_position(market_id)
        if position is not None and position.status == "open":
            exposure += max(0.0, position.notional)
    return exposure


def _paper_probe_trade_size_usdc(config, probe_signal: Signal) -> float:
    if probe_signal.reason.startswith("微型探索仓:"):
        return min(1.0, max(0.0, float(config.risk.paper_probe_trade_size_usdc)))
    return max(0.0, float(config.risk.paper_probe_trade_size_usdc))


def _recent_zero_taker_runs(output_dir: str) -> int:
    path = Path(output_dir) / "paper_report.csv"
    if not path.exists():
        return 0
    with path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    streak = 0
    for row in reversed(rows):
        if int(float(row.get("taker_count") or 0)) > 0:
            break
        streak += 1
    return streak


def _paper_probe_signal(config, market, history, market_config, current_signal: Signal, btc_candles, disabled_probe_families: set[str] | None = None) -> Signal | None:
    if _paper_probe_blocked_by_hard_risk(current_signal.reason):
        return None
    disabled_probe_families = disabled_probe_families or set()
    market_type = classify_market(market).market_type
    if market_type == "range_bucket":
        center_probe = _paper_range_bucket_center_probe_signal(
            config, market, history, market_config, current_signal, btc_candles, disabled_probe_families
        )
        if center_probe is not None:
            return center_probe
        return _paper_range_bucket_probe_signal(
            config, market, history, market_config, current_signal, btc_candles, disabled_probe_families
        )
    if market_type == "touch_below":
        no_probe = _paper_touch_below_no_probe_signal(
            config, market, history, market_config, current_signal, btc_candles, disabled_probe_families
        )
        if no_probe is not None:
            return no_probe
        certainty_no_probe = _paper_touch_below_certainty_no_probe_signal(
            config, market, history, market_config, current_signal, btc_candles, disabled_probe_families
        )
        if certainty_no_probe is not None:
            return certainty_no_probe
        distance_no_probe = _paper_touch_below_distance_no_probe_signal(
            config, market, history, market_config, current_signal, btc_candles, disabled_probe_families
        )
        if distance_no_probe is not None:
            return distance_no_probe
        momentum_yes_probe = _paper_touch_below_momentum_yes_probe_signal(
            config, market, history, market_config, current_signal, btc_candles, disabled_probe_families
        )
        if momentum_yes_probe is not None:
            return momentum_yes_probe
        discount_probe = _paper_touch_below_discount_probe_signal(
            config, market, history, market_config, current_signal, btc_candles, disabled_probe_families
        )
        if discount_probe is not None:
            return discount_probe
        if "touch_below_yes" in disabled_probe_families:
            return None
        return _paper_touch_below_probe_signal(config, market, history, market_config, current_signal, btc_candles)
    if market_type != "above_below_expiry":
        return None
    if current_signal.reason.startswith("当前市场类型暂不交易"):
        return None
    if len(history) < market_config.signal.long_window:
        return None
    if "阻止 BUY_NO" in current_signal.reason and current_signal.net_edge >= max(config.risk.paper_probe_min_edge, 0.01):
        challenge_disabled = "regime_filter_challenge" in disabled_probe_families
        challenge_reversal_blocked = _above_below_no_reversal_risk_blocks_probe(
            config, market, history[-1].timestamp, btc_candles
        )
        current_yes = history[-1].price
        no_price = max(0.0, 1.0 - current_yes)
        if (
            not challenge_disabled
            and not challenge_reversal_blocked
            and config.risk.min_price < no_price < config.risk.range_buy_no_max_price
        ):
            return Signal(
                "BUY_NO",
                min(0.30, current_signal.net_edge / 0.08),
                current_signal.edge,
                current_signal.net_edge,
                f"过滤器挑战仓: 小仓位验证被 BTC regime 拦截的 above_below_expiry/NO; 原因={current_signal.reason}",
            )
    near_strike_no_signal = _paper_near_strike_above_below_no_probe_signal(
        config, market, history, current_signal, btc_candles, disabled_probe_families
    )
    if near_strike_no_signal is not None:
        return near_strike_no_signal
    certainty_signal = _paper_above_below_certainty_no_probe_signal(
        config, market, history, current_signal, btc_candles, disabled_probe_families
    )
    if certainty_signal is not None:
        return certainty_signal
    ultra_certainty_no_signal = _paper_above_below_ultra_certainty_no_probe_signal(
        config, market, history, current_signal, btc_candles, disabled_probe_families
    )
    if ultra_certainty_no_signal is not None:
        return ultra_certainty_no_signal
    crossed_reversal_no_signal = _paper_above_below_crossed_reversal_no_probe_signal(
        config, market, history, current_signal, btc_candles, disabled_probe_families
    )
    if crossed_reversal_no_signal is not None:
        return crossed_reversal_no_signal
    certainty_yes_signal = _paper_above_below_certainty_yes_probe_signal(
        config, market, history, current_signal, btc_candles, disabled_probe_families
    )
    if certainty_yes_signal is not None:
        return certainty_yes_signal
    ultra_certainty_yes_signal = _paper_above_below_ultra_certainty_yes_probe_signal(
        config, market, history, current_signal, btc_candles, disabled_probe_families
    )
    if ultra_certainty_yes_signal is not None:
        return ultra_certainty_yes_signal
    expensive_no_signal = _paper_expensive_edge_above_below_no_probe_signal(
        config, market, history, current_signal, btc_candles, disabled_probe_families
    )
    if expensive_no_signal is not None:
        return expensive_no_signal
    recovery_no_signal = _paper_above_below_recovery_no_probe_signal(
        config, market, history, current_signal, btc_candles, disabled_probe_families
    )
    if recovery_no_signal is not None:
        return recovery_no_signal
    current = history[-1]
    if "暂不允许 BUY_YES" in current_signal.reason and current_signal.net_edge >= config.risk.paper_probe_min_edge:
        if "above_below_yes" in disabled_probe_families:
            return None
        if current.price <= config.risk.min_price or current.price >= config.risk.range_buy_yes_max_price:
            return None
        if _above_below_yes_reversal_risk_blocks_probe(config, market, current.timestamp, btc_candles):
            return None
        strike_blocked, _ = blocks_btc_strike_entry(market, current.timestamp, btc_candles, "BUY_YES")
        range_blocked, _ = blocks_price_range_entry(
            market,
            "BUY_YES",
            current.timestamp,
            btc_candles,
            current.price,
            config.risk.range_buy_yes_max_price,
            config.risk.range_buy_no_max_price,
            config.risk.range_market_safety_band_pct,
            config.risk.btc_moving_away_return_pct,
        )
        regime_blocked, _ = blocks_directional_entry(market, Signal("BUY_YES", current_signal.confidence, current_signal.edge, current_signal.net_edge, current_signal.reason), btc_candles, current.timestamp)
        if strike_blocked or range_blocked or regime_blocked:
            return None
        return Signal(
            "BUY_YES",
            min(0.35, current_signal.net_edge / max(config.risk.paper_probe_min_edge * 5, 0.0001)),
            current_signal.edge,
            current_signal.net_edge,
            f"探索仓: 连续零成交后，仅用小仓位验证 above_below_expiry/YES; 原因={current_signal.reason}",
        )
    if infer_strike_direction(market.question) != "above":
        return None
    if "above_below_no" in disabled_probe_families:
        return None
    prices = [point.price for point in history]
    current_yes = prices[-1]
    no_price = max(0.0, 1.0 - current_yes)
    if no_price <= config.risk.min_price or no_price >= config.risk.range_buy_no_max_price:
        return None
    short_avg = mean(prices[-market_config.signal.short_window :])
    long_avg = mean(prices[-market_config.signal.long_window :])
    no_momentum = long_avg - short_avg
    costs = estimate_entry_cost(
        no_price,
        market.effective_taker_fee_rate(market_config.backtest.taker_fee_rate),
        market_config.backtest.slippage_bps,
        market_config.signal.safety_margin,
    )
    no_net_edge = no_momentum - costs.total_rate
    if no_net_edge < config.risk.paper_probe_min_edge:
        return None
    range_blocked, _ = blocks_price_range_entry(
        market,
        "BUY_NO",
        history[-1].timestamp,
        btc_candles,
        history[-1].price,
        config.risk.range_buy_yes_max_price,
        config.risk.range_buy_no_max_price,
        config.risk.range_market_safety_band_pct,
        config.risk.btc_moving_away_return_pct,
    )
    regime_blocked, _ = blocks_directional_entry(market, Signal("BUY_NO", 0.0, no_momentum, no_net_edge, current_signal.reason), btc_candles, history[-1].timestamp)
    if range_blocked or regime_blocked:
        return None
    return Signal(
        "BUY_NO",
        min(0.35, no_net_edge / max(config.risk.paper_probe_min_edge * 5, 0.0001)),
        no_momentum,
        no_net_edge,
        f"探索仓: 连续零成交后，仅用小仓位验证 above_below_expiry/NO; 原因={current_signal.reason}",
    )


def _paper_probe_blocked_by_hard_risk(reason: str) -> bool:
    return "同类方向连续止损" in reason or "亏损暂停" in reason or "触发止损" in reason


def _is_paper_probe_reason(reason: str) -> bool:
    return "探索仓" in reason or "挑战仓" in reason


def _underperforming_probe_families(config, storage) -> set[str]:
    closed_positions = storage.load_closed_paper_position_history()
    rows = build_probe_performance_report(
        config.backtest.output_dir,
        closed_positions,
        storage.load_open_paper_market_ids(),
    )
    disabled = set()
    for row in rows:
        if row.closed_count >= 20 and row.average_realized_pnl < 0:
            disabled.add(row.probe_family)
        elif row.closed_count >= 3 and row.average_realized_pnl < -0.05:
            disabled.add(row.probe_family)
        elif row.closed_count >= 2 and row.average_realized_pnl < -0.25:
            disabled.add(row.probe_family)
        elif row.closed_count >= 1 and row.average_realized_pnl <= -0.5:
            disabled.add(row.probe_family)
        elif row.closed_count >= 1 and row.realized_pnl <= -1.0:
            disabled.add(row.probe_family)
    entry_families = _paper_probe_entry_families(config.backtest.output_dir)
    for position in closed_positions:
        family = entry_families.get((position.market_id, position.opened_at))
        if family is not None and position.realized_pnl <= -0.5:
            disabled.add(family)
    return disabled


def _paper_range_bucket_probe_signal(
    config,
    market,
    history,
    market_config,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "range_bucket_yes" in disabled_probe_families:
        return None
    bounds = _extract_range_bounds(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, history[-1].timestamp)
    if bounds is None or candle is None or candle.close <= 0:
        return None
    lower, upper = bounds
    if not lower < candle.close < upper:
        return None
    width = upper - lower
    if width <= 0:
        return None
    boundary_distance_pct = min(candle.close - lower, upper - candle.close) / candle.close
    min_boundary_distance_pct = max(config.risk.range_market_safety_band_pct / 3, 0.003)
    if boundary_distance_pct < min_boundary_distance_pct:
        return None
    high_certainty_price_cap = 0.985 if current_signal.net_edge >= 0.05 else min(config.risk.range_buy_yes_max_price, 0.85)
    if history[-1].price <= config.risk.min_price or history[-1].price >= high_certainty_price_cap:
        return None
    if current_signal.net_edge < max(config.risk.paper_probe_min_edge, 0.01):
        return None
    return Signal(
        "BUY_YES",
        min(0.35, current_signal.net_edge / 0.05),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 连续零成交后，小仓位验证 range_bucket/YES; "
            f"BTC={candle.close:.2f}, range=[{lower:.0f},{upper:.0f}], boundary_distance={boundary_distance_pct:.2%}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_range_bucket_center_probe_signal(
    config,
    market,
    history,
    market_config,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "range_bucket_center_yes" in disabled_probe_families:
        return None
    if not current_signal.reason.startswith("当前市场类型暂不交易"):
        return None
    bounds = _extract_range_bounds(market.question)
    current = history[-1]
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if bounds is None or candle is None or candle.close <= 0:
        return None
    lower, upper = bounds
    if not lower < candle.close < upper:
        return None
    width = upper - lower
    if width <= 0:
        return None
    boundary_distance_pct = min(candle.close - lower, upper - candle.close) / candle.close
    center = (lower + upper) / 2
    center_offset_ratio = abs(candle.close - center) / (width / 2)
    if boundary_distance_pct < max(config.risk.range_market_safety_band_pct / 2, 0.006):
        return None
    if center_offset_ratio > 0.35:
        return None
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    if return_1h is not None and abs(return_1h) > 0.006:
        return None
    if current_signal.net_edge < max(0.05, config.risk.paper_probe_min_edge * 25):
        return None
    if current.price <= config.risk.min_price or current.price >= 0.98:
        return None
    return Signal(
        "BUY_YES",
        min(0.18, current_signal.net_edge / 0.35),
        current_signal.edge,
        current_signal.net_edge,
        (
            "微型探索仓: 1USDC 验证区间中心 range_bucket/YES v1; "
            f"yes={current.price:.3f}, BTC={candle.close:.2f}, range=[{lower:.0f},{upper:.0f}], "
            f"boundary_distance={boundary_distance_pct:.2%}, center_offset={center_offset_ratio:.2f}, "
            f"1h={_fmt_pct(return_1h)}; 原因={current_signal.reason}"
        ),
    )


def _paper_near_strike_above_below_no_probe_signal(
    config,
    market,
    history,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "near_strike_above_below_no" in disabled_probe_families:
        return None
    if not (
        current_signal.reason.startswith("BTC 正接近 above strike")
        or current_signal.reason.startswith("BTC 1h 正接近 above strike")
        or current_signal.reason.startswith("BTC 未明显远离 above strike")
        or current_signal.reason.startswith("BTC 1h 未明显远离 above strike")
    ):
        return None
    if infer_strike_direction(market.question) != "above":
        return None
    if current_signal.net_edge < max(0.08, config.risk.paper_probe_min_edge * 20):
        return None
    current = history[-1]
    yes_price = current.price
    no_price = max(0.0, 1.0 - yes_price)
    if no_price <= config.risk.min_price or no_price > min(config.risk.range_buy_no_max_price, 0.75):
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (strike - candle.close) / candle.close
    min_distance_pct = max(0.004, config.risk.range_market_safety_band_pct / 4)
    if distance_pct < min_distance_pct or distance_pct > config.risk.range_market_safety_band_pct:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_away_from_strike = (return_15m is not None and return_15m <= -0.001) or (
        return_1h is not None and return_1h <= -0.002
    )
    if not moving_away_from_strike:
        return None
    return Signal(
        "BUY_NO",
        min(0.20, current_signal.net_edge / 0.30),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 小仓位验证 near-strike 安全带 above_below_expiry/NO; "
            f"no={no_price:.3f}, BTC={candle.close:.2f}, strike={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _above_below_no_reversal_risk_blocks_probe(config, market, timestamp: int, btc_candles) -> bool:
    if infer_strike_direction(market.question) != "above":
        return False
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return True
    distance_pct = (strike - candle.close) / candle.close
    if distance_pct <= 0:
        return True
    safety_band = max(config.risk.range_market_safety_band_pct, 0.01)
    if distance_pct > safety_band:
        return False
    return_15m = _btc_return_since(btc_candles, timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, timestamp, 60 * 60, candle.close)
    moving_away_threshold = max(config.risk.btc_moving_away_return_pct, 0.001)
    moving_away_from_strike = (return_15m is not None and return_15m <= -moving_away_threshold) or (
        return_1h is not None and return_1h <= -2 * moving_away_threshold
    )
    return not moving_away_from_strike


def _above_below_yes_reversal_risk_blocks_probe(config, market, timestamp: int, btc_candles) -> bool:
    if infer_strike_direction(market.question) != "above":
        return False
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return True
    distance_pct = (candle.close - strike) / candle.close
    min_distance_pct = max(0.012, config.risk.range_market_safety_band_pct / 2)
    if distance_pct < min_distance_pct:
        return True
    return_15m = _btc_return_since(btc_candles, timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, timestamp, 60 * 60, candle.close)
    return (return_15m is not None and return_15m <= -0.003) or (
        return_1h is not None and return_1h <= -0.006
    )


def _paper_above_below_certainty_no_probe_signal(
    config,
    market,
    history,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "certainty_above_below_no" in disabled_probe_families:
        return None
    if not current_signal.reason.startswith("NO 价格太接近 1"):
        return None
    if current_signal.net_edge < max(config.risk.paper_probe_min_edge, 0.05):
        return None
    if infer_strike_direction(market.question) != "above":
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, history[-1].timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (strike - candle.close) / candle.close
    min_distance_pct = max(0.005, config.risk.range_market_safety_band_pct / 4)
    if distance_pct < min_distance_pct:
        return None
    yes_price = history[-1].price
    no_price = max(0.0, 1.0 - yes_price)
    if no_price <= config.risk.range_buy_no_max_price or no_price > 0.985:
        return None
    return Signal(
        "BUY_NO",
        min(0.20, current_signal.net_edge / 0.20),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 小仓位验证高确定性 above_below_expiry/NO; "
            f"BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_above_below_ultra_certainty_no_probe_signal(
    config,
    market,
    history,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "ultra_certainty_above_below_no" in disabled_probe_families:
        return None
    if not current_signal.reason.startswith("NO 价格太接近 1"):
        return None
    if current_signal.net_edge < max(0.01, config.risk.paper_probe_min_edge * 8):
        return None
    if infer_strike_direction(market.question) != "above":
        return None
    current = history[-1]
    yes_price = current.price
    no_price = max(0.0, 1.0 - yes_price)
    if no_price <= 0.94 or no_price > 0.999:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (strike - candle.close) / candle.close
    if distance_pct < max(0.02, config.risk.range_market_safety_band_pct) or distance_pct > 0.12:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_toward_strike = (return_15m is not None and return_15m >= 0.0075) or (
        return_1h is not None and return_1h >= 0.012
    )
    if moving_toward_strike:
        return None
    return Signal(
        "BUY_NO",
        min(0.08, current_signal.net_edge / 0.25),
        current_signal.edge,
        current_signal.net_edge,
        (
            "微型探索仓: 1USDC 验证超高确定性 above_below_expiry/NO v1; "
            f"no={no_price:.3f}, BTC={candle.close:.2f}, strike={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_above_below_crossed_reversal_no_probe_signal(
    config,
    market,
    history,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "crossed_above_reversal_no" in disabled_probe_families:
        return None
    if current_signal.action != "BUY_NO" and "阻止 BUY_NO" not in current_signal.reason:
        return None
    if infer_strike_direction(market.question) != "above":
        return None
    if current_signal.net_edge < max(0.04, config.risk.paper_probe_min_edge * 20):
        return None
    current = history[-1]
    yes_price = current.price
    no_price = max(0.0, 1.0 - yes_price)
    if no_price < 0.20 or no_price > 0.70:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    crossed_distance_pct = (candle.close - strike) / candle.close
    if crossed_distance_pct <= 0 or crossed_distance_pct > 0.025:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    if return_1h is None or return_1h > -0.002:
        return None
    if return_15m is not None and return_15m > 0.006:
        return None
    return Signal(
        "BUY_NO",
        min(0.10, current_signal.net_edge / 0.35),
        current_signal.edge,
        current_signal.net_edge,
        (
            "微型探索仓: 1USDC 验证 crossed-above 回落 above_below_expiry/NO v1; "
            f"no={no_price:.3f}, BTC={candle.close:.2f}, strike={strike:.2f}, "
            f"crossed={crossed_distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_above_below_certainty_yes_probe_signal(
    config,
    market,
    history,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "certainty_above_below_yes" in disabled_probe_families:
        return None
    if not current_signal.reason.startswith("above_below_expiry 暂不允许 BUY_YES"):
        return None
    if infer_strike_direction(market.question) != "above":
        return None
    if current_signal.net_edge < max(0.03, config.risk.paper_probe_min_edge * 20):
        return None
    current = history[-1]
    yes_price = current.price
    if yes_price <= 0.70 or yes_price > 0.925:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (candle.close - strike) / candle.close
    min_distance_pct = max(0.012, config.risk.range_market_safety_band_pct / 2)
    if distance_pct < min_distance_pct or distance_pct > 0.12:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_toward_strike = (return_15m is not None and return_15m <= -0.003) or (
        return_1h is not None and return_1h <= -0.006
    )
    if moving_toward_strike:
        return None
    return Signal(
        "BUY_YES",
        min(0.18, current_signal.net_edge / 0.30),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 小仓位验证高确定性 above_below_expiry/YES v1; "
            f"yes={yes_price:.3f}, BTC={candle.close:.2f}, strike={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_above_below_ultra_certainty_yes_probe_signal(
    config,
    market,
    history,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "ultra_certainty_above_below_yes" in disabled_probe_families:
        return None
    if not current_signal.reason.startswith("above_below_expiry 暂不允许 BUY_YES"):
        return None
    if infer_strike_direction(market.question) != "above":
        return None
    if current_signal.net_edge < max(0.015, config.risk.paper_probe_min_edge * 10):
        return None
    current = history[-1]
    yes_price = current.price
    if yes_price <= 0.90 or yes_price > 0.965:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (candle.close - strike) / candle.close
    if distance_pct < max(0.035, config.risk.range_market_safety_band_pct * 1.75) or distance_pct > 0.15:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_toward_strike = (return_15m is not None and return_15m <= -0.0075) or (
        return_1h is not None and return_1h <= -0.012
    )
    if moving_toward_strike:
        return None
    return Signal(
        "BUY_YES",
        min(0.10, current_signal.net_edge / 0.30),
        current_signal.edge,
        current_signal.net_edge,
        (
            "微型探索仓: 1USDC 验证超高确定性 above_below_expiry/YES v1; "
            f"yes={yes_price:.3f}, BTC={candle.close:.2f}, strike={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_above_below_recovery_no_probe_signal(
    config,
    market,
    history,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "recovery_above_below_no" in disabled_probe_families:
        return None
    if not current_signal.reason.startswith("range-like BUY_NO 价格过高"):
        return None
    if infer_strike_direction(market.question) != "above":
        return None
    if current_signal.net_edge < max(0.08, config.risk.paper_probe_min_edge * 50):
        return None
    current = history[-1]
    yes_price = current.price
    no_price = max(0.0, 1.0 - yes_price)
    if no_price <= config.risk.range_buy_no_max_price or no_price > 0.925:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (strike - candle.close) / candle.close
    min_distance_pct = max(0.012, config.risk.range_market_safety_band_pct / 2)
    if distance_pct < min_distance_pct or distance_pct > 0.08:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    if return_15m is None or return_1h is None:
        return None
    moving_toward_strike = return_15m >= 0.002 or return_1h >= 0.005
    if moving_toward_strike:
        return None
    regime_blocked, _ = blocks_directional_entry(
        market,
        Signal("BUY_NO", current_signal.confidence, current_signal.edge, current_signal.net_edge, current_signal.reason),
        btc_candles,
        current.timestamp,
    )
    if regime_blocked:
        return None
    return Signal(
        "BUY_NO",
        min(0.14, current_signal.net_edge / 0.40),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 样本恢复 above_below_expiry/NO v1; "
            f"no={no_price:.3f}, BTC={candle.close:.2f}, strike={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_expensive_edge_above_below_no_probe_signal(
    config,
    market,
    history,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "expensive_edge_above_below_no" in disabled_probe_families:
        return None
    if not current_signal.reason.startswith("range-like BUY_NO 价格过高"):
        return None
    if infer_strike_direction(market.question) != "above":
        return None
    current = history[-1]
    yes_price = current.price
    no_price = max(0.0, 1.0 - yes_price)
    max_probe_no_price = min(0.92, config.risk.max_price)
    if no_price <= config.risk.range_buy_no_max_price or no_price > max_probe_no_price:
        return None
    if current_signal.net_edge < max(0.05, config.risk.paper_probe_min_edge * 10):
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (strike - candle.close) / candle.close
    min_distance_pct = max(0.004, config.risk.range_market_safety_band_pct / 4)
    if distance_pct < min_distance_pct:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_toward_strike = (return_15m is not None and return_15m >= 0.002) or (
        return_1h is not None and return_1h >= 0.005
    )
    if moving_toward_strike:
        return None
    regime_blocked, _ = blocks_directional_entry(
        market,
        Signal("BUY_NO", current_signal.confidence, current_signal.edge, current_signal.net_edge, current_signal.reason),
        btc_candles,
        current.timestamp,
    )
    if regime_blocked:
        return None
    return Signal(
        "BUY_NO",
        min(0.25, current_signal.net_edge / 0.20),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 小仓位验证高价正edge above_below_expiry/NO; "
            f"no={no_price:.3f}, BTC={candle.close:.2f}, strike={strike:.2f}, distance={distance_pct:.2%}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_touch_below_probe_signal(config, market, history, market_config, current_signal: Signal, btc_candles) -> Signal | None:
    if "暂不允许 BUY_YES" not in current_signal.reason:
        return None
    current = history[-1]
    high_certainty = current_signal.net_edge >= 0.05
    price_cap = 0.85 if high_certainty else config.risk.target_buy_yes_max_price
    if current.price <= config.risk.min_price or current.price >= price_cap:
        return None
    if current_signal.net_edge < max(config.risk.paper_probe_min_edge, market_config.signal.min_edge):
        return None
    target_blocked, _ = blocks_price_target_entry(
        market,
        "BUY_YES",
        current.timestamp,
        btc_candles,
        config.risk.target_market_max_distance_pct,
        current.price,
        price_cap,
        config.risk.target_buy_no_max_price,
        config.risk.btc_moving_away_return_pct,
    )
    regime_blocked, _ = blocks_directional_entry(
        market,
        Signal("BUY_YES", current_signal.confidence, current_signal.edge, current_signal.net_edge, current_signal.reason),
        btc_candles,
        current.timestamp,
    )
    if target_blocked or regime_blocked:
        return None
    return Signal(
        "BUY_YES",
        min(0.30, current_signal.net_edge / 0.08),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 连续零成交后，小仓位验证 touch_below/YES; "
            f"price_cap={price_cap:.3f}, high_certainty={high_certainty}; 原因={current_signal.reason}"
        ),
    )


def _paper_touch_below_no_probe_signal(
    config,
    market,
    history,
    market_config,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "touch_below_no" in disabled_probe_families:
        return None
    if "touch_below 暂不允许 BUY_NO" not in current_signal.reason:
        return None
    if infer_strike_direction(market.question) != "below":
        return None
    current = history[-1]
    yes_price = current.price
    no_price = max(0.0, 1.0 - yes_price)
    if current_signal.net_edge < max(0.06, config.risk.paper_probe_min_edge * 30):
        return None
    if no_price <= config.risk.range_buy_no_max_price or no_price > 0.94:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (candle.close - strike) / candle.close
    if distance_pct <= 0.008 or distance_pct > 0.045:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_toward_dip = (return_15m is not None and return_15m <= -0.003) or (
        return_1h is not None and return_1h <= -0.006
    )
    if moving_toward_dip:
        return None
    regime_blocked, _ = blocks_directional_entry(
        market,
        Signal("BUY_NO", current_signal.confidence, current_signal.edge, current_signal.net_edge, current_signal.reason),
        btc_candles,
        current.timestamp,
    )
    if regime_blocked:
        return None
    return Signal(
        "BUY_NO",
        min(0.20, current_signal.net_edge / 0.20),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 小仓位验证 touch_below/NO v1; "
            f"no={no_price:.3f}, BTC={candle.close:.2f}, target={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_touch_below_certainty_no_probe_signal(
    config,
    market,
    history,
    market_config,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "touch_below_certainty_no" in disabled_probe_families:
        return None
    if "touch_below 暂不允许 BUY_NO" not in current_signal.reason:
        return None
    if infer_strike_direction(market.question) != "below":
        return None
    current = history[-1]
    yes_price = current.price
    no_price = max(0.0, 1.0 - yes_price)
    if current_signal.net_edge < max(0.025, config.risk.paper_probe_min_edge * 20):
        return None
    if no_price <= 0.94 or no_price > 0.985:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (candle.close - strike) / candle.close
    if distance_pct <= 0.015 or distance_pct > 0.055:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_toward_dip = (return_15m is not None and return_15m <= -0.004) or (
        return_1h is not None and return_1h <= -0.003
    )
    if moving_toward_dip:
        return None
    regime_blocked, _ = blocks_directional_entry(
        market,
        Signal("BUY_NO", current_signal.confidence, current_signal.edge, current_signal.net_edge, current_signal.reason),
        btc_candles,
        current.timestamp,
    )
    if regime_blocked:
        return None
    return Signal(
        "BUY_NO",
        min(0.16, current_signal.net_edge / 0.25),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 小仓位验证高确定性 touch_below/NO v2; "
            f"no={no_price:.3f}, BTC={candle.close:.2f}, target={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_touch_below_distance_no_probe_signal(
    config,
    market,
    history,
    market_config,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "touch_below_distance_no" in disabled_probe_families:
        return None
    positive_edge_skip = current_signal.reason.startswith("净优势不足") or "touch_below 暂不允许 BUY_NO" in current_signal.reason
    if not positive_edge_skip:
        return None
    if infer_strike_direction(market.question) != "below":
        return None
    current = history[-1]
    yes_price = current.price
    no_price = max(0.0, 1.0 - yes_price)
    if current_signal.net_edge < max(0.035, config.risk.paper_probe_min_edge * 20):
        return None
    if no_price < 0.25 or no_price > 0.72:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (candle.close - strike) / candle.close
    if distance_pct < 0.055 or distance_pct > 0.28:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_toward_dip = (return_15m is not None and return_15m <= -0.0025) or (
        return_1h is not None and return_1h <= -0.006
    )
    if moving_toward_dip:
        return None
    regime_blocked, _ = blocks_directional_entry(
        market,
        Signal("BUY_NO", current_signal.confidence, current_signal.edge, current_signal.net_edge, current_signal.reason),
        btc_candles,
        current.timestamp,
    )
    if regime_blocked:
        return None
    return Signal(
        "BUY_NO",
        min(0.12, current_signal.net_edge / 0.30),
        current_signal.edge,
        current_signal.net_edge,
        (
            "微型探索仓: 1USDC 验证距离安全 touch_below/NO v1; "
            f"no={no_price:.3f}, BTC={candle.close:.2f}, target={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_touch_below_momentum_yes_probe_signal(
    config,
    market,
    history,
    market_config,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "touch_below_momentum_yes" in disabled_probe_families:
        return None
    if "touch_below 暂不允许 BUY_YES" not in current_signal.reason:
        return None
    if infer_strike_direction(market.question) != "below":
        return None
    current = history[-1]
    if current_signal.net_edge < max(0.08, config.risk.paper_probe_min_edge * 40):
        return None
    if current.price <= 0.18 or current.price >= 0.72:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (candle.close - strike) / candle.close
    if distance_pct <= 0.004 or distance_pct > 0.035:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_toward_target = (return_15m is not None and return_15m <= -0.0015) or (
        return_1h is not None and return_1h <= -0.003
    )
    if not moving_toward_target:
        return None
    regime_blocked, _ = blocks_directional_entry(
        market,
        Signal("BUY_YES", current_signal.confidence, current_signal.edge, current_signal.net_edge, current_signal.reason),
        btc_candles,
        current.timestamp,
    )
    if regime_blocked:
        return None
    return Signal(
        "BUY_YES",
        min(0.20, current_signal.net_edge / 0.25),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 小仓位验证 touch_below/YES momentum v1; "
            f"yes={current.price:.3f}, BTC={candle.close:.2f}, target={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _paper_touch_below_discount_probe_signal(
    config,
    market,
    history,
    market_config,
    current_signal: Signal,
    btc_candles,
    disabled_probe_families: set[str] | None = None,
) -> Signal | None:
    if disabled_probe_families and "touch_below_discount_yes" in disabled_probe_families:
        return None
    if not current_signal.reason.startswith("净优势不足"):
        return None
    if infer_strike_direction(market.question) != "below":
        return None
    current = history[-1]
    if current_signal.net_edge < max(0.035, config.risk.paper_probe_min_edge * 15):
        return None
    if current.price <= 0.25 or current.price >= 0.78:
        return None
    strike = extract_usd_strike(market.question)
    candle = latest_btc_candle_at_or_before(btc_candles, current.timestamp)
    if strike is None or candle is None or candle.close <= 0:
        return None
    distance_pct = (candle.close - strike) / candle.close
    if distance_pct <= 0.005 or distance_pct > 0.045:
        return None
    return_15m = _btc_return_since(btc_candles, current.timestamp, 15 * 60, candle.close)
    return_1h = _btc_return_since(btc_candles, current.timestamp, 60 * 60, candle.close)
    moving_toward_target = (return_15m is not None and return_15m <= -0.001) or (
        return_1h is not None and return_1h <= -0.002
    )
    if not moving_toward_target:
        return None
    regime_blocked, _ = blocks_directional_entry(
        market,
        Signal("BUY_YES", current_signal.confidence, current_signal.edge, current_signal.net_edge, current_signal.reason),
        btc_candles,
        current.timestamp,
    )
    if regime_blocked:
        return None
    return Signal(
        "BUY_YES",
        min(0.25, current_signal.net_edge / 0.12),
        current_signal.edge,
        current_signal.net_edge,
        (
            "探索仓: 小仓位验证折扣 touch_below/YES v2; "
            f"yes={current.price:.3f}, BTC={candle.close:.2f}, target={strike:.2f}, "
            f"distance={distance_pct:.2%}, 15m={_fmt_pct(return_15m)}, 1h={_fmt_pct(return_1h)}; "
            f"原因={current_signal.reason}"
        ),
    )


def _btc_return_since(candles, timestamp: int, lookback_seconds: int, current_close: float) -> float | None:
    previous = latest_btc_candle_at_or_before(candles, timestamp - lookback_seconds)
    if previous is None or previous.close == 0:
        return None
    return (current_close - previous.close) / previous.close


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"

def _extract_range_bounds(question: str) -> tuple[float, float] | None:
    values = []
    for value, suffix in re.findall(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]+)?)(k)?", question.lower()):
        amount = float(value.replace(",", ""))
        if suffix:
            amount *= 1000
        values.append(amount)
    if len(values) < 2:
        return None
    lower, upper = sorted(values[:2])
    return lower, upper


def _live_paper_entry_plan(config, market, signal, market_config, reference_yes_price: float):
    default_plan = plan_execution(market, signal, market_config.signal, market_config.backtest, market_config.execution, reference_yes_price)
    if signal.action not in {"BUY_YES", "BUY_NO"}:
        return signal, default_plan
    token_id = market.yes_token_id if signal.action == "BUY_YES" else market.no_token_id
    if not token_id:
        hold = Signal("HOLD", 0.0, signal.edge, signal.net_edge, "缺少对应 token，无法读取实时 ask")
        return hold, plan_execution(market, hold, market_config.signal, market_config.backtest, market_config.execution, reference_yes_price)
    try:
        quote = get_token_quote(config, token_id)
    except HttpError as exc:
        hold = Signal("HOLD", 0.0, signal.edge, signal.net_edge, f"实时 ask 获取失败，跳过模拟开仓: {exc}")
        return hold, plan_execution(market, hold, market_config.signal, market_config.backtest, market_config.execution, reference_yes_price)
    if quote.ask is None:
        hold = Signal("HOLD", 0.0, signal.edge, signal.net_edge, "订单簿缺少实时 ask，跳过模拟开仓")
        return hold, plan_execution(market, hold, market_config.signal, market_config.backtest, market_config.execution, reference_yes_price)
    if quote.spread is None or quote.spread > config.risk.max_spread:
        hold = Signal("HOLD", 0.0, signal.edge, signal.net_edge, f"实时订单簿价差过宽或不完整，跳过模拟开仓: spread={quote.spread}")
        return hold, plan_execution(market, hold, market_config.signal, market_config.backtest, market_config.execution, reference_yes_price)
    reference_side_price = reference_yes_price if signal.action == "BUY_YES" else max(0.0, 1.0 - reference_yes_price)
    adverse_repricing = max(0.0, quote.ask - reference_side_price)
    repriced_edge = signal.net_edge - adverse_repricing
    required_edge = (
        config.risk.paper_probe_min_edge
        if _is_paper_probe_reason(signal.reason)
        else market_config.signal.min_edge * max(1.0, config.risk.live_reprice_edge_multiplier)
    )
    if repriced_edge < required_edge:
        hold = Signal(
            "HOLD",
            0.0,
            signal.edge,
            repriced_edge,
            f"实时 ask 重定价后净 edge 不足，跳过模拟开仓: ask={quote.ask:.3f}, required={required_edge:.4f}",
        )
        return hold, plan_execution(market, hold, market_config.signal, market_config.backtest, market_config.execution, reference_yes_price)
    repriced_signal = Signal(signal.action, signal.confidence, signal.edge, repriced_edge, f"{signal.reason}; 实时 ask 已确认")
    return (
        repriced_signal,
        plan_execution(market, repriced_signal, market_config.signal, market_config.backtest, market_config.execution, reference_yes_price, quote.ask),
    )


def _paper_position_state_signal(config, storage, market, yes_price: float, run_timestamp: int, current_side_price: float | None = None) -> Signal | None:
    position = storage.load_paper_position(market.id)
    if position is None:
        return None

    if position.status == "open":
        current_price = current_side_price if current_side_price is not None else _paper_side_price(position.side, yes_price)
        peak_price = max(position.peak_price, position.entry_price, current_price)
        pnl_pct = (current_price - position.entry_price) / position.entry_price if position.entry_price > 0 else 0.0
        peak_pnl_pct = (peak_price - position.entry_price) / position.entry_price if position.entry_price > 0 else 0.0
        trailing_drawdown_pct = peak_pnl_pct - pnl_pct
        updated_position = _replace_paper_position(position, peak_price=peak_price)

        if pnl_pct <= -config.risk.stop_loss_pct:
            realized_pnl = _paper_close_value(position, current_price, market, config)
            cooldown_seconds = (
                config.risk.target_stop_cooldown_seconds
                if is_target_like_market_type(classify_market(market).market_type)
                else config.risk.paper_reentry_cooldown_seconds
            )
            cooldown_until = run_timestamp + cooldown_seconds
            storage.close_paper_position(market.id, run_timestamp, realized_pnl, cooldown_until)
            return Signal("HOLD", 0.0, 0.0, 0.0, f"模拟持仓触发止损，进入同市场冷却; pnl_pct={pnl_pct:.1%}; cooldown_until={cooldown_until}")
        elif pnl_pct >= config.risk.paper_full_take_profit_pct:
            realized_pnl = _paper_close_value(position, current_price, market, config)
            cooldown_until = run_timestamp + config.risk.paper_take_profit_reentry_cooldown_seconds
            storage.close_paper_position(market.id, run_timestamp, realized_pnl, cooldown_until)
            return Signal("HOLD", 0.0, 0.0, 0.0, f"模拟持仓触发全量止盈，短冷却后可重新评估; pnl_pct={pnl_pct:.1%}; cooldown_until={cooldown_until}")
        elif (
            peak_pnl_pct >= config.risk.trailing_stop_activation_pct
            and trailing_drawdown_pct >= config.risk.trailing_stop_drawdown_pct
        ):
            realized_pnl = _paper_close_value(position, current_price, market, config)
            cooldown_until = run_timestamp + config.risk.paper_take_profit_reentry_cooldown_seconds
            storage.close_paper_position(market.id, run_timestamp, realized_pnl, cooldown_until)
            return Signal(
                "HOLD",
                0.0,
                0.0,
                0.0,
                f"模拟持仓触发移动止盈，保护已产生利润; pnl_pct={pnl_pct:.1%}; peak_pnl_pct={peak_pnl_pct:.1%}; cooldown_until={cooldown_until}",
            )
        elif pnl_pct >= config.risk.partial_take_profit_pct and position.partial_take_profit_count == 0:
            updated_position, partial_realized_pnl = _paper_partial_close(position, current_price, market, config)
            updated_position = _replace_paper_position(
                updated_position,
                peak_price=peak_price,
                partial_take_profit_count=position.partial_take_profit_count + 1,
            )
            storage.update_open_paper_position(updated_position)
            return Signal(
                "HOLD",
                0.0,
                0.0,
                0.0,
                f"模拟持仓分批止盈，已兑现 {config.risk.partial_take_profit_fraction:.0%}; pnl_pct={pnl_pct:.1%}; realized_pnl={partial_realized_pnl:.2f}; 剩余仓位继续跟踪",
            )

        if updated_position.peak_price != position.peak_price:
            storage.update_open_paper_position(updated_position)
        return Signal(
            "HOLD",
            0.0,
            0.0,
            0.0,
            f"已有模拟持仓 {position.side}，不重复开同一市场; pnl_pct={pnl_pct:.1%}; peak_pnl_pct={peak_pnl_pct:.1%}; partial_tp={position.partial_take_profit_count}",
        )

    if position.cooldown_until > run_timestamp:
        return Signal("HOLD", 0.0, 0.0, 0.0, f"同一市场冷却中，cooldown_until={position.cooldown_until}")
    return None


def _paper_settlement_signal(config, storage, market, position: PaperPositionState, run_timestamp: int) -> Signal | None:
    try:
        resolved_market = get_market_by_id(config, market.id, use_cache=False)
    except HttpError:
        return None
    if resolved_market is None or not resolved_market.closed or resolved_market.resolution_status != "resolved":
        return None
    settlement_price = _resolved_side_price(resolved_market, position.side)
    if settlement_price is None:
        return None
    storage.save_markets([resolved_market])
    realized_pnl = position.realized_pnl + position.shares * settlement_price - position.notional
    storage.close_paper_position(market.id, run_timestamp, realized_pnl, run_timestamp)
    return Signal(
        "HOLD",
        0.0,
        0.0,
        0.0,
        f"模拟持仓按已解析结果结算; side={position.side}; payout={settlement_price:.0f}; realized_pnl={realized_pnl:.2f}",
    )


def _paper_market_end_date_has_passed(market, run_timestamp: int) -> bool:
    if not market.end_date:
        return False
    try:
        raw_value = str(market.end_date)
        if raw_value.endswith("Z"):
            raw_value = raw_value[:-1] + "+00:00"
        end_time = datetime.fromisoformat(raw_value)
    except ValueError:
        return False
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    return end_time.timestamp() <= run_timestamp


def _resolved_side_price(market, side: str) -> float | None:
    yes_price = market.yes_price
    no_price = market.no_price
    if yes_price is None or no_price is None:
        return None
    if not (
        (yes_price >= 0.999 and no_price <= 0.001)
        or (no_price >= 0.999 and yes_price <= 0.001)
    ):
        return None
    return yes_price if side == "YES" else no_price


def _paper_reentry_edge_too_weak(config, storage, market, expected_net_edge: float, min_edge: float) -> bool:
    position = storage.load_paper_position(market.id)
    if position is None or position.status != "closed" or position.realized_pnl <= 0:
        return False
    required_edge = min_edge * config.risk.paper_reentry_edge_multiplier
    return expected_net_edge < required_edge


def _strategy_loss_pause_blocks_entry(config, storage, market, action: str, timestamp: int) -> tuple[bool, str]:
    if action not in {"BUY_YES", "BUY_NO"}:
        return False, ""
    max_losses = max(0, int(config.risk.strategy_loss_pause_count))
    if max_losses <= 0:
        return False, ""
    side = "NO" if action == "BUY_NO" else "YES"
    market_type = classify_market(market).market_type
    direction = infer_strike_direction(market.question)
    since_timestamp = timestamp - max(0, int(config.risk.strategy_loss_pause_window_seconds))
    if direction != "unknown":
        losses = storage.count_recent_paper_losses_by_direction(market_type, direction, side, since_timestamp)
    else:
        losses = storage.count_recent_paper_losses(market_type, side, since_timestamp)
    if losses >= max_losses:
        return (
            True,
            f"同类方向连续止损/亏损暂停: market_type={market_type}, direction={direction}, side={side}, losses={losses}, window={config.risk.strategy_loss_pause_window_seconds}s",
        )
    return False, ""


def _paper_close_value(position: PaperPositionState, current_price: float, market, config) -> float:
    gross_proceeds = position.shares * current_price
    fee = fee_amount(gross_proceeds, current_price, market.effective_taker_fee_rate(config.backtest.taker_fee_rate))
    return position.realized_pnl + gross_proceeds - fee - position.notional


def _paper_partial_close(position: PaperPositionState, current_price: float, market, config) -> tuple[PaperPositionState, float]:
    fraction = min(max(config.risk.partial_take_profit_fraction, 0.0), 1.0)
    if fraction <= 0.0:
        return position, 0.0
    shares_sold = position.shares * fraction
    cost_basis_sold = position.notional * fraction
    gross_proceeds = shares_sold * current_price
    fee = fee_amount(gross_proceeds, current_price, market.effective_taker_fee_rate(config.backtest.taker_fee_rate))
    partial_realized_pnl = gross_proceeds - fee - cost_basis_sold
    return (
        _replace_paper_position(
            position,
            shares=position.shares - shares_sold,
            notional=position.notional - cost_basis_sold,
            realized_pnl=position.realized_pnl + partial_realized_pnl,
        ),
        partial_realized_pnl,
    )


def _replace_paper_position(position: PaperPositionState, **changes) -> PaperPositionState:
    values = {
        "market_id": position.market_id,
        "side": position.side,
        "entry_price": position.entry_price,
        "shares": position.shares,
        "notional": position.notional,
        "opened_at": position.opened_at,
        "status": position.status,
        "closed_at": position.closed_at,
        "realized_pnl": position.realized_pnl,
        "cooldown_until": position.cooldown_until,
        "peak_price": position.peak_price,
        "partial_take_profit_count": position.partial_take_profit_count,
    }
    values.update(changes)
    return PaperPositionState(**values)


def _save_paper_position(config, storage, market, execution_plan, run_timestamp: int, notional_override: float | None = None) -> None:
    if execution_plan.side not in {"BUY_YES", "BUY_NO"} or execution_plan.limit_price is None:
        return
    side = "NO" if execution_plan.side == "BUY_NO" else "YES"
    entry_price = execution_plan.limit_price
    entry_fee_rate = taker_fee_rate(entry_price, market.effective_taker_fee_rate(config.backtest.taker_fee_rate))
    slippage_rate = config.backtest.slippage_bps / 10_000
    notional = notional_override if notional_override is not None else config.backtest.trade_size_usdc
    cost_basis = notional + notional * entry_fee_rate + notional * slippage_rate
    execution_price = entry_price * (1 + slippage_rate)
    if execution_price <= 0:
        return
    storage.save_open_paper_position(
        PaperPositionState(
            market_id=market.id,
            side=side,
            entry_price=execution_price,
            shares=notional / execution_price,
            notional=cost_basis,
            opened_at=run_timestamp,
            status="open",
            closed_at=None,
            realized_pnl=0.0,
            cooldown_until=0,
            peak_price=execution_price,
            partial_take_profit_count=0,
        )
    )


def _paper_side_price(side: str, yes_price: float) -> float:
    return yes_price if side == "YES" else max(0.0, 1.0 - yes_price)


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


def _run_paper_sample_report(config, recent_runs: int) -> None:
    rows = build_paper_sample_report(config.backtest.output_dir, recent_runs=recent_runs)
    path = write_paper_sample_report_csv(rows, config.backtest.output_dir)
    print_paper_sample_report(rows)
    print(f"paper_sample_report_csv={path}")


def _run_live_universe_report(config, recent_runs: int) -> None:
    try:
        markets = discover_btc_markets(config, use_cache=False)
    except HttpError as exc:
        raise SystemExit(f"Live discovery failed; not falling back to historical SQLite markets: {exc}") from exc
    sample_rows = build_paper_sample_report(config.backtest.output_dir, recent_runs=recent_runs)
    rows = build_live_universe_report(markets, sample_rows)
    path = write_live_universe_report_csv(rows, config.backtest.output_dir)
    print_live_universe_report(rows)
    print(f"live_universe_report_csv={path}")


def _run_strategy_review(config, recent_runs: int) -> None:
    rows = build_strategy_review(config.backtest.output_dir, recent_runs=recent_runs)
    path = write_strategy_review_csv(rows, config.backtest.output_dir)
    print_strategy_review(rows)
    storage = storage_from_config(config)
    account = storage.load_paper_account_summary()
    total_open_exposure = _paper_open_exposure_usdc(storage)
    probe_open_exposure = _paper_open_probe_exposure_usdc(config, storage)
    probe_open_count = len(_paper_open_probe_positions(config, storage))
    probe_slots = _paper_probe_available_slots(config, storage)
    zero_taker_streak = _recent_zero_taker_runs(config.backtest.output_dir)
    print(
        f"strategy_review_slots | open_positions={account.open_position_count} | "
        f"probe_open_positions={probe_open_count} | "
        f"probe_soft_max_open={config.risk.paper_probe_max_open_positions} | "
        f"probe_hard_max_open={config.risk.paper_probe_hard_max_open_positions} | "
        f"total_open_exposure={total_open_exposure:.2f} | "
        f"probe_open_exposure={probe_open_exposure:.2f} | "
        f"probe_max_exposure={config.risk.paper_probe_max_total_exposure_usdc:.2f} | "
        f"zero_taker_streak={zero_taker_streak} | "
        f"probe_slots={probe_slots}"
    )
    disabled_families = sorted(_underperforming_probe_families(config, storage))
    print(f"strategy_review_disabled_probe_families | count={len(disabled_families)} | families={','.join(disabled_families) or 'none'}")
    print(f"strategy_review_csv={path}")


def _run_filter_reason_report(config, recent_runs: int) -> None:
    rows = build_filter_reason_report(config.backtest.output_dir, recent_runs=recent_runs)
    path = write_filter_reason_report_csv(rows, config.backtest.output_dir)
    print_filter_reason_report(rows)
    print(f"filter_reason_report_csv={path}")


def _run_blocked_edge_report(config, recent_runs: int) -> None:
    rows = build_blocked_edge_report(config.backtest.output_dir, recent_runs=recent_runs)
    path = write_blocked_edge_report_csv(rows, config.backtest.output_dir)
    print_blocked_edge_report(rows)
    print(f"blocked_edge_report_csv={path}")


def _run_touch_below_path_report(config, recent_runs: int) -> None:
    btc_candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    rows = build_touch_below_path_report(config.backtest.output_dir, btc_candles, recent_runs=recent_runs)
    path = write_touch_below_path_report_csv(rows, config.backtest.output_dir)
    print_touch_below_path_report(rows)
    print(f"touch_below_path_report_csv={path}")


def _run_probe_performance_report(config) -> None:
    storage = storage_from_config(config)
    rows = build_probe_performance_report(
        config.backtest.output_dir,
        storage.load_closed_paper_position_history(),
        storage.load_open_paper_market_ids(),
    )
    path = write_probe_performance_report_csv(rows, config.backtest.output_dir)
    print_probe_performance_report(rows)
    print(f"probe_performance_report_csv={path}")


def _run_strategy_autotune_report(config, recent_runs: int) -> None:
    storage = storage_from_config(config)
    strategy_rows = build_strategy_review(config.backtest.output_dir, recent_runs=recent_runs)
    probe_rows = build_probe_performance_report(
        config.backtest.output_dir,
        storage.load_closed_paper_position_history(),
        storage.load_open_paper_market_ids(),
    )
    context = AutotuneContext(
        open_positions=storage.load_paper_account_summary().open_position_count,
        probe_slots=_paper_probe_available_slots(config, storage),
        open_exposure_usdc=_paper_open_probe_exposure_usdc(config, storage),
        probe_max_exposure_usdc=config.risk.paper_probe_max_total_exposure_usdc,
        disabled_probe_families=sorted(_underperforming_probe_families(config, storage)),
        zero_taker_streak=_recent_zero_taker_runs(config.backtest.output_dir),
        probe_zero_run_threshold=config.risk.paper_probe_zero_run_threshold,
    )
    rows = build_strategy_autotune_report(strategy_rows, probe_rows, context)
    path = write_strategy_autotune_report_csv(rows, config.backtest.output_dir)
    print_strategy_autotune_report(rows)
    print(f"strategy_autotune_report_csv={path}")


def _run_open_position_report(config, live_quotes: bool) -> None:
    storage = storage_from_config(config)
    markets = storage.load_markets()
    market_by_id = {market.id: market for market in markets}
    positions = []
    for market_id in storage.load_open_paper_market_ids():
        position = storage.load_paper_position(market_id)
        if position is not None and position.status == "open":
            positions.append(position)
    live_side_prices = {}
    if live_quotes:
        for position in positions:
            market = market_by_id.get(position.market_id)
            token_id = None if market is None else (market.yes_token_id if position.side == "YES" else market.no_token_id)
            if not token_id:
                continue
            try:
                quote = get_token_quote(config, token_id)
            except HttpError:
                continue
            live_side_prices[position.market_id] = quote.bid
    rows = build_open_position_report(config.backtest.output_dir, markets, positions, int(time()), live_side_prices)
    path = write_open_position_report_csv(rows, config.backtest.output_dir)
    print_open_position_report(rows)
    print(f"open_position_report_csv={path}")


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
    snapshot_stats = storage_from_config(config).snapshot_stats()
    print("local SQLite storage")
    print(f"- enabled: {stats.enabled}")
    print(f"- sqlite_path: {stats.sqlite_path}")
    print(f"- markets: {stats.market_count}")
    print(f"- price_points: {stats.price_point_count}")
    print(f"- paper_snapshots: {snapshot_stats.snapshot_count}")


def _run_data_quality(config) -> None:
    stats = storage_from_config(config).market_history_stats()
    print_data_quality_summary(stats)
    path = write_data_quality_csv(stats, config.backtest.output_dir)
    print(f"data_quality_csv={path}")


def _run_btc_price(config) -> None:
    csv_path = Path(config.backtest.output_dir) / "btc_price_candles.csv"
    existing = load_btc_candles_csv(csv_path)
    try:
        candles = get_btc_candles(config, use_cache=False)
        source = "live"
    except HttpError as exc:
        print(f"warning: live BTC candles failed: {exc}", file=sys.stderr)
        candles = existing
        source = "local_csv"
        if not candles:
            candles = get_btc_candles(config, use_cache=True)
            source = "http_cache"
    candles = merge_btc_candles(existing, candles)
    path = write_btc_candles_csv(candles, config.backtest.output_dir)
    latest = candles[-1] if candles else None
    if latest is None:
        print(f"btc_price | candles=0 | {path}")
        return
    print(
        f"btc_price | provider={config.btc_price.provider} | product={config.btc_price.product_id} | source={source} | "
        f"candles={len(candles)} | latest_close={latest.close:.2f} | {path}"
    )


def _run_alignment_report(config, market_type: str, max_points_per_market: int | None = None) -> None:
    storage = storage_from_config(config)
    markets = _filter_markets(storage.load_markets(), market_type)
    candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    if not candles:
        candles = get_btc_candles(config)
        write_btc_candles_csv(candles, config.backtest.output_dir)
    rows = build_alignment_rows(markets, storage, candles, [1, 3, 6], max_points_per_market=max_points_per_market)
    summaries = summarize_alignment(rows)
    rows_path = write_alignment_rows_csv(rows, config.backtest.output_dir)
    summary_path = write_alignment_summary_csv(summaries, config.backtest.output_dir)
    print_alignment_summary(summaries)
    print(f"alignment_csv={rows_path}")
    print(f"alignment_summary_csv={summary_path}")


def _run_edge_report(config, min_samples: int) -> None:
    alignment_path = Path(config.backtest.output_dir) / "alignment_report.csv"
    if not alignment_path.exists():
        raise SystemExit("No alignment rows found. Run alignment-report first.")
    buckets = build_edge_buckets_from_csv(alignment_path, min_samples=min_samples)
    path = write_edge_report_csv(buckets, config.backtest.output_dir)
    print_edge_report_summary(buckets)
    print(f"edge_report_csv={path}")


def _run_strategy_sweep(config, market_type: str, limit: int, candidate_limit: int | None, max_points_per_market: int | None = None) -> None:
    storage = storage_from_config(config)
    markets = storage.load_markets()
    btc_candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    if limit <= 0:
        raise SystemExit("--limit must be > 0")
    if candidate_limit is not None and candidate_limit <= 0:
        raise SystemExit("--candidate-limit must be > 0")
    if max_points_per_market is not None and max_points_per_market <= 0:
        raise SystemExit("--max-points-per-market must be > 0")
    if not markets:
        raise SystemExit("No local markets found. Run discover or backtest first.")
    if not btc_candles:
        raise SystemExit("No BTC candles found. Run btc-price first.")
    results = run_strategy_sweep(config, storage, markets, btc_candles, market_type, limit, candidate_limit, max_points_per_market)
    path = write_strategy_sweep_csv(results, config.backtest.output_dir)
    print_strategy_sweep_summary(results, path)


def _run_spread_scan(config, market_type: str) -> None:
    storage = storage_from_config(config)
    markets = _filter_markets(_spread_markets(config, storage), market_type)
    if not markets:
        rows = []
        path = write_spread_scan_csv(rows, config.backtest.output_dir)
        print("spread_scan | data_degraded=true | markets=0 | reason=live market discovery unavailable; local cache not used for realtime scan")
        print_spread_scan_summary(rows, path)
        return
    rows = scan_spreads(config, markets, storage)
    path = write_spread_scan_csv(rows, config.backtest.output_dir)
    print_spread_scan_summary(rows, path)


def _run_reversal_backtest(config, market_type: str) -> None:
    storage = storage_from_config(config)
    markets = _filter_markets(storage.load_markets(), market_type)
    if not markets:
        raise SystemExit("No local markets found. Run discover or backtest first.")
    results = []
    strategies = default_reversal_strategies()
    for market in markets:
        history = _safe_history(config, market, storage, prefer_local=True, use_cache=True)
        if not history:
            continue
        for strategy in strategies:
            results.append(run_reversal_backtest(config, market, history, strategy))
    rows = summarize_reversal_results(results)
    summary_path = write_reversal_summary_csv(rows, config.backtest.output_dir)
    trades_path = write_reversal_trades_csv(results, config.backtest.output_dir)
    print_reversal_summary(rows, summary_path)
    print(f"reversal_trades_csv={trades_path}")


def _run_flow_scan(config, market_type: str, limit: int, large_trade_usdc: float) -> None:
    storage = storage_from_config(config)
    markets = _filter_markets(_flow_markets(config, storage), market_type)
    if not markets:
        raise SystemExit("No markets found. Run discover first.")
    candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    if not candles:
        candles = get_btc_candles(config, use_cache=False)
        write_btc_candles_csv(candles, config.backtest.output_dir)
    rows = scan_market_flows(config, markets, candles, limit_per_market=limit, large_trade_usdc=large_trade_usdc)
    path = write_flow_scan_csv(rows, config.backtest.output_dir)
    print_flow_scan_summary(rows, path)


def _flow_markets(config, storage):
    try:
        live_markets = discover_btc_markets(config, use_cache=False)
    except Exception as exc:
        print(f"warning: live market discovery failed for flow-scan: {exc}", file=sys.stderr)
        live_markets = []
    if live_markets:
        storage.save_markets(live_markets)
        return live_markets
    return storage.load_markets()


def _spread_markets(config, storage):
    return _discover_live_markets_or_empty(config, storage, "spread-scan")


def _run_market_type_report(config) -> None:
    storage = storage_from_config(config)
    markets = storage.load_markets()
    if not markets:
        raise SystemExit("No local markets found. Run discover or backtest first.")
    candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    if not candles:
        candles = get_btc_candles(config)
        write_btc_candles_csv(candles, config.backtest.output_dir)
    rows = build_market_type_report(config, storage, candles)
    path = write_market_type_report_csv(rows, config.backtest.output_dir)
    print_market_type_report(rows, path)


def _run_observation_report(config, recent_runs: int) -> None:
    rows = build_observation_report(config.backtest.output_dir, recent_runs)
    path = write_observation_report_csv(rows, config.backtest.output_dir)
    print_observation_report(rows, path)


def _run_side_diagnostics(config) -> None:
    rows = build_side_diagnostics(config.backtest.output_dir)
    path = write_side_diagnostics_csv(rows, config.backtest.output_dir)
    print_side_diagnostics(rows, path)


def _run_strike_report(config) -> None:
    rows = build_strike_report(Path(config.backtest.output_dir) / "backtest_summary.csv")
    path = write_strike_report_csv(rows, config.backtest.output_dir)
    print_strike_report(rows, path)


def _run_daily_report(config) -> None:
    storage = storage_from_config(config)
    paper_account = storage.load_paper_account_summary()
    report = build_daily_report(
        config.backtest.output_dir,
        config.risk.readiness_max_drawdown_pct,
        paper_account.realized_pnl,
        paper_account.open_position_count,
        paper_account.closed_position_count,
    )
    path = write_daily_report_csv(report, config.backtest.output_dir)
    print(
        f"daily_report | readiness={report.readiness} | paper_runs={report.paper_runs} | "
        f"trades={report.replay_trade_count} | replay_pnl={report.replay_pnl:.2f} | "
        f"paper_account_pnl={report.paper_account_pnl:.2f} | "
        f"paper_positions=open:{report.paper_account_open_positions}/closed:{report.paper_account_closed_positions} | "
        f"max_drawdown={report.replay_max_drawdown:.1%} | "
        f"live_health={report.live_pipeline_healthy}/{report.live_pipeline_reason} | "
        f"spread_buy_both={report.spread_buy_both_count} | best_buy_edge={report.spread_best_buy_edge:.4f} | "
        f"reason={report.reason}"
    )
    print(f"daily_report_csv={path}")


if __name__ == "__main__":
    main()
