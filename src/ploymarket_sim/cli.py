from __future__ import annotations

import argparse
import sys

from .backtest import backtest_market
from .clob import get_price_history
from .config import load_config
from .http import HttpError
from .polymarket import discover_btc_markets
from .reporting import print_market_table, print_signal, write_backtest_csv
from .signals import build_signal


DEFAULT_CONFIG = "config/default.toml"


def main() -> None:
    parser = argparse.ArgumentParser(description="BTC prediction-market research simulator")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("discover", help="find active BTC-related prediction markets")
    subparsers.add_parser("signals", help="print current signals for discovered markets")
    subparsers.add_parser("backtest", help="run a simple historical paper-trading backtest")
    subparsers.add_parser("explain-risk", help="explain the current risk limits")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "discover":
        print_market_table(discover_btc_markets(config))
    elif args.command == "signals":
        for market in discover_btc_markets(config):
            history = _safe_history(config, market)
            if not history:
                continue
            print_signal(market, build_signal(market, history, config.signal, config.backtest))
    elif args.command == "backtest":
        for market in discover_btc_markets(config):
            history = _safe_history(config, market)
            if not history:
                continue
            result = backtest_market(market, history, config)
            path = write_backtest_csv(result, config.backtest.output_dir)
            trade_count = len([trade for trade in result.trades if trade.action != "REJECTED"])
            total_fees = sum(trade.fee for trade in result.trades)
            total_slippage = sum(trade.slippage for trade in result.trades)
            print(
                f"{market.id} | trades={trade_count} | pnl={result.realized_pnl:.2f} | "
                f"fees={total_fees:.2f} | slippage={total_slippage:.2f} | ending_cash={result.ending_cash:.2f} | {path}"
            )
    elif args.command == "explain-risk":
        _explain_risk(config)


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


if __name__ == "__main__":
    main()
