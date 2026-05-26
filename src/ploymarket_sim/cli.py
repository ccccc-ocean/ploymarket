from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import sleep, time

from .alignment import build_alignment_rows, summarize_alignment
from .backtest import backtest_market
from .btc_regime import blocks_directional_entry
from .btc_price import get_btc_candles, load_btc_candles_csv, merge_btc_candles
from .cache import CachePolicy, JsonCache
from .classifier import MARKET_TYPES, is_market_type
from .clob import get_price_history, get_token_quote
from .config import load_config
from .costs import fee_amount, taker_fee_rate
from .cross_platform import match_btc_markets, print_cross_platform_summary, write_cross_platform_matches_csv
from .daily_report import build_daily_report, write_daily_report_csv
from .edge_report import build_edge_buckets, load_alignment_rows_csv
from .execution import ExecutionPlan, plan_execution
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
from .http import HttpError
from .kalshi import discover_kalshi_btc_markets
from .market_rules import blocks_btc_strike_entry, blocks_price_target_entry
from .market_type_report import build_market_type_report, print_market_type_report, write_market_type_report_csv
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
from .spread_scan import print_spread_scan_summary, scan_spreads, write_spread_scan_csv
from .storage import PaperPositionState, storage_from_config
from .strategy_profiles import is_tradeable_market, strategy_config_for_market
from .strategy_sweep import print_strategy_sweep_summary, run_strategy_sweep, write_strategy_sweep_csv
from .strike_report import build_strike_report, print_strike_report, write_strike_report_csv
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
    subparsers.add_parser("btc-price", help="fetch external BTC spot candles")
    alignment_parser = subparsers.add_parser("alignment-report", help="align local Polymarket YES history with BTC candles")
    alignment_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="price_target")
    edge_parser = subparsers.add_parser("edge-report", help="bucket alignment rows to inspect conditional edge")
    edge_parser.add_argument("--min-samples", type=int, default=30)
    sweep_parser = subparsers.add_parser("strategy-sweep", help="try conservative 5-minute strategy parameter candidates")
    sweep_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="price_target")
    sweep_parser.add_argument("--limit", type=int, default=10)
    spread_parser = subparsers.add_parser("spread-scan", help="scan live YES/NO order books for complete-set spread edges")
    spread_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="price_target")
    reversal_parser = subparsers.add_parser("reversal-backtest", help="compare BUY_YES, BUY_NO, reversal, and stop-loss variants")
    reversal_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="price_range_daily")
    flow_parser = subparsers.add_parser("flow-scan", help="scan recent Polymarket trade flow and large-wallet pressure")
    flow_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="all")
    flow_parser.add_argument("--limit", type=int, default=250)
    flow_parser.add_argument("--large-trade-usdc", type=float, default=500.0)
    subparsers.add_parser("market-type-report", help="compare local backtest results by BTC market type")
    subparsers.add_parser("strike-report", help="summarize BTC daily range backtest results by strike")
    subparsers.add_parser("kalshi-discover", help="find active BTC-related Kalshi markets")
    cross_parser = subparsers.add_parser("cross-platform-report", help="match Polymarket and Kalshi BTC markets")
    cross_parser.add_argument("--market-type", choices=["all"] + MARKET_TYPES, default="price_range_daily")
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
        _run_alignment_report(config, args.market_type)
    elif args.command == "edge-report":
        _run_edge_report(config, args.min_samples)
    elif args.command == "strategy-sweep":
        _run_strategy_sweep(config, args.market_type, args.limit)
    elif args.command == "spread-scan":
        _run_spread_scan(config, args.market_type)
    elif args.command == "reversal-backtest":
        _run_reversal_backtest(config, args.market_type)
    elif args.command == "flow-scan":
        _run_flow_scan(config, args.market_type, args.limit, args.large_trade_usdc)
    elif args.command == "market-type-report":
        _run_market_type_report(config)
    elif args.command == "strike-report":
        _run_strike_report(config)
    elif args.command == "kalshi-discover":
        _run_kalshi_discover(config)
    elif args.command == "cross-platform-report":
        _run_cross_platform_report(config, args.market_type)
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
    markets = _filter_markets(_paper_markets(config, storage), market_type)
    btc_candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    btc_candles = _fresh_paper_btc_candles(config, btc_candles, run_timestamp)
    rows = []
    stress_candidates = []
    for market in markets:
        history = _safe_history(config, market, storage, prefer_local=False, use_cache=False, allow_local_fallback=False)
        if not history:
            continue
        storage.save_price_history(market.yes_token_id or "", history)
        market_config = strategy_config_for_market(config, market)
        state_signal = _paper_position_signal_with_live_quote(config, storage, market, history[-1].price, run_timestamp)
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
            blocked, reason = blocks_price_target_entry(
                market,
                signal.action,
                history[-1].timestamp,
                btc_candles,
                config.risk.target_market_max_distance_pct,
                history[-1].price,
                config.risk.target_buy_yes_max_price,
                config.risk.target_buy_no_max_price,
            )
            if blocked:
                signal = Signal("HOLD", 0.0, signal.edge, signal.net_edge, reason)
            blocked, reason = blocks_directional_entry(market, signal, btc_candles, history[-1].timestamp)
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
        if execution_plan.mode == "TAKER":
            stress_candidate = build_paper_signal_row(
                market, signal, config.backtest.taker_fee_rate, run_timestamp, execution_plan
            )
            stress_candidates.append(stress_candidate)
            blocked, reason = _paper_execution_stress_blocks_entry(config, stress_candidate)
            if blocked:
                signal = Signal("HOLD", 0.0, signal.edge, signal.net_edge, reason)
                execution_plan = ExecutionPlan("SKIP", "", None, 0.0, stress_candidate.expected_net_edge, reason)
        if execution_plan.mode == "TAKER":
            _save_paper_position(config, storage, market, execution_plan, run_timestamp)
        rows.append(build_paper_signal_row(market, signal, config.backtest.taker_fee_rate, run_timestamp, execution_plan))
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
            f"partial_cancels={stress_summary.partial_fill_cancels} | fail_safe={stress_summary.fail_safe_scenarios} | "
            f"{stress_path} | events={event_path}"
        )
        print(
            f"execution_stress_report | runs={history.runs} | candidates={history.candidates} | "
            f"robust={history.robust_candidates} | latency_blocked={history.latency_blocked_candidates} | "
            f"partial_cancels={history.partial_fill_cancels} | fail_safe={history.fail_safe_scenarios} | "
            f"{history_path}"
        )


def _paper_markets(config, storage):
    return _discover_live_markets_or_empty(config, storage, "paper-run")


def _paper_execution_stress_blocks_entry(config, candidate) -> tuple[bool, str]:
    if not config.execution_stress.enabled:
        return False, ""
    rows = build_execution_stress_rows([candidate], config.execution_stress, config.backtest.trade_size_usdc)
    summary = summarize_execution_stress(rows)
    if summary.robust_candidates == 1:
        return False, ""
    failed_scenarios = [
        row.scenario
        for row in rows
        if row.outcome == "BLOCK" and (row.scenario == "baseline" or row.scenario.startswith("latency_adverse_"))
    ]
    reason = "执行压力拒绝开仓：实时 ask 候选无法在延迟价格恶化后保留最低净 edge"
    if failed_scenarios:
        reason += f" ({', '.join(failed_scenarios)})"
    return True, reason


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


def _paper_position_signal_with_live_quote(config, storage, market, yes_price: float, run_timestamp: int) -> Signal | None:
    position = storage.load_paper_position(market.id)
    if position is None or position.status != "open":
        return _paper_position_state_signal(config, storage, market, yes_price, run_timestamp)
    token_id = market.yes_token_id if position.side == "YES" else market.no_token_id
    if not token_id:
        return Signal("HOLD", 0.0, 0.0, 0.0, "已有模拟持仓，但缺少对应 token，无法用实时 bid 退出")
    try:
        quote = get_token_quote(config, token_id)
    except HttpError as exc:
        return Signal("HOLD", 0.0, 0.0, 0.0, f"已有模拟持仓，但实时 bid 获取失败，暂停退出判断: {exc}")
    if quote.bid is None:
        return Signal("HOLD", 0.0, 0.0, 0.0, "已有模拟持仓，但订单簿缺少实时 bid，暂停退出判断")
    return _paper_position_state_signal(config, storage, market, yes_price, run_timestamp, quote.bid)


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
    if repriced_edge < market_config.signal.min_edge:
        hold = Signal("HOLD", 0.0, signal.edge, repriced_edge, f"实时 ask 重定价后净 edge 不足，跳过模拟开仓: ask={quote.ask:.3f}")
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
                if classify_market(market).market_type in {"price_target", "price_target_daily"}
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


def _paper_reentry_edge_too_weak(config, storage, market, expected_net_edge: float, min_edge: float) -> bool:
    position = storage.load_paper_position(market.id)
    if position is None or position.status != "closed" or position.realized_pnl <= 0:
        return False
    required_edge = min_edge * config.risk.paper_reentry_edge_multiplier
    return expected_net_edge < required_edge


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


def _save_paper_position(config, storage, market, execution_plan, run_timestamp: int) -> None:
    if execution_plan.side not in {"BUY_YES", "BUY_NO"} or execution_plan.limit_price is None:
        return
    side = "NO" if execution_plan.side == "BUY_NO" else "YES"
    entry_price = execution_plan.limit_price
    entry_fee_rate = taker_fee_rate(entry_price, market.effective_taker_fee_rate(config.backtest.taker_fee_rate))
    slippage_rate = config.backtest.slippage_bps / 10_000
    notional = config.backtest.trade_size_usdc
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


def _run_kalshi_discover(config) -> None:
    markets = discover_kalshi_btc_markets(config, use_cache=False)
    print(f"kalshi_markets | count={len(markets)}")
    for market in markets[:25]:
        yes = market.mid_yes_price
        yes_label = f"{yes:.3f}" if yes is not None else "n/a"
        print(f"- {market.ticker} | yes={yes_label} | vol24h={market.volume_24h:.0f} | close={market.close_time} | {market.question}")


def _run_cross_platform_report(config, market_type: str) -> None:
    storage = storage_from_config(config)
    polymarket_markets = _filter_markets(storage.load_markets(), market_type)
    if not polymarket_markets:
        polymarket_markets = _filter_markets(_discover_markets_with_quality_guard(config, storage, "cross-platform-report"), market_type)
    kalshi_markets = discover_kalshi_btc_markets(config, use_cache=False)
    rows = match_btc_markets(polymarket_markets, kalshi_markets)
    path = write_cross_platform_matches_csv(rows, config.backtest.output_dir)
    print_cross_platform_summary(rows, path)


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


def _run_alignment_report(config, market_type: str) -> None:
    storage = storage_from_config(config)
    markets = _filter_markets(storage.load_markets(), market_type)
    candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    if not candles:
        candles = get_btc_candles(config)
        write_btc_candles_csv(candles, config.backtest.output_dir)
    rows = build_alignment_rows(markets, storage, candles, [1, 3, 6])
    summaries = summarize_alignment(rows)
    rows_path = write_alignment_rows_csv(rows, config.backtest.output_dir)
    summary_path = write_alignment_summary_csv(summaries, config.backtest.output_dir)
    print_alignment_summary(summaries)
    print(f"alignment_csv={rows_path}")
    print(f"alignment_summary_csv={summary_path}")


def _run_edge_report(config, min_samples: int) -> None:
    alignment_path = Path(config.backtest.output_dir) / "alignment_report.csv"
    rows = load_alignment_rows_csv(alignment_path)
    if not rows:
        raise SystemExit("No alignment rows found. Run alignment-report first.")
    buckets = build_edge_buckets(rows, min_samples=min_samples)
    path = write_edge_report_csv(buckets, config.backtest.output_dir)
    print_edge_report_summary(buckets)
    print(f"edge_report_csv={path}")


def _run_strategy_sweep(config, market_type: str, limit: int) -> None:
    storage = storage_from_config(config)
    markets = storage.load_markets()
    btc_candles = load_btc_candles_csv(Path(config.backtest.output_dir) / "btc_price_candles.csv")
    if limit <= 0:
        raise SystemExit("--limit must be > 0")
    if not markets:
        raise SystemExit("No local markets found. Run discover or backtest first.")
    if not btc_candles:
        raise SystemExit("No BTC candles found. Run btc-price first.")
    results = run_strategy_sweep(config, storage, markets, btc_candles, market_type, limit)
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


def _run_strike_report(config) -> None:
    rows = build_strike_report(Path(config.backtest.output_dir) / "backtest_summary.csv")
    path = write_strike_report_csv(rows, config.backtest.output_dir)
    print_strike_report(rows, path)


def _run_daily_report(config) -> None:
    report = build_daily_report(config.backtest.output_dir)
    path = write_daily_report_csv(report, config.backtest.output_dir)
    print(
        f"daily_report | readiness={report.readiness} | paper_runs={report.paper_runs} | "
        f"trades={report.replay_trade_count} | pnl={report.replay_pnl:.2f} | "
        f"max_drawdown={report.replay_max_drawdown:.1%} | "
        f"spread_buy_both={report.spread_buy_both_count} | best_buy_edge={report.spread_best_buy_edge:.4f} | "
        f"reason={report.reason}"
    )
    print(f"daily_report_csv={path}")


if __name__ == "__main__":
    main()
