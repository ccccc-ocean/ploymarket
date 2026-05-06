from __future__ import annotations

import csv
from pathlib import Path

from .backtest import BacktestResult
from .polymarket import Market
from .signals import Signal


def print_market_table(markets: list[Market]) -> None:
    print(f"found {len(markets)} BTC-related markets")
    for market in markets:
        print(
            f"- {market.id} | yes={market.yes_price:.3f} | liq={market.liquidity:.0f} | "
            f"vol24h={market.volume_24hr:.0f} | {market.question}"
        )


def print_signal(market: Market, signal: Signal) -> None:
    print(f"{market.id} | {signal.action} | edge={signal.edge:.4f} | confidence={signal.confidence:.2f}")
    print(f"  {market.question}")
    print(f"  reason: {signal.reason}")


def write_backtest_csv(result: BacktestResult, output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"backtest_{result.market_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "market_id", "action", "price", "notional", "pnl", "reason"])
        for trade in result.trades:
            writer.writerow(
                [trade.timestamp, trade.market_id, trade.action, trade.price, trade.notional, trade.pnl, trade.reason]
            )
    return path
