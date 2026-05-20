from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path

from .backtest import backtest_market
from .btc_price import BtcCandle
from .classifier import MARKET_TYPES, is_market_type
from .config import AppConfig
from .portfolio import build_portfolio_curve, summarize_portfolio
from .storage import Storage
from .summary import aggregate_summaries, summarize_market


@dataclass(frozen=True)
class MarketTypeReportRow:
    market_type: str
    market_count: int
    traded_market_count: int
    trade_count: int
    win_rate: float
    pnl: float
    total_fees: float
    total_slippage: float
    max_drawdown: float
    ending_equity: float


def build_market_type_report(
    config: AppConfig,
    storage: Storage,
    btc_candles: list[BtcCandle],
) -> list[MarketTypeReportRow]:
    markets = storage.load_markets()
    rows = []
    for market_type in MARKET_TYPES:
        typed_markets = [market for market in markets if is_market_type(market, market_type)]
        if not typed_markets:
            continue
        results = []
        summaries = []
        for market in typed_markets:
            history = storage.load_price_history(market.yes_token_id or "")
            if not history:
                continue
            result = backtest_market(market, history, config, btc_candles)
            results.append(result)
            summaries.append(summarize_market(market, result))
        if not summaries:
            rows.append(MarketTypeReportRow(market_type, len(typed_markets), 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, config.risk.starting_cash))
            continue
        aggregate = aggregate_summaries(summaries)[0]
        portfolio_summary = summarize_portfolio(build_portfolio_curve(results, config), config) if results else None
        rows.append(
            MarketTypeReportRow(
                market_type=market_type,
                market_count=aggregate.market_count,
                traded_market_count=aggregate.traded_market_count,
                trade_count=aggregate.trade_count,
                win_rate=aggregate.win_rate,
                pnl=aggregate.realized_pnl,
                total_fees=aggregate.total_fees,
                total_slippage=aggregate.total_slippage,
                max_drawdown=portfolio_summary.max_drawdown if portfolio_summary else 0.0,
                ending_equity=portfolio_summary.ending_equity if portfolio_summary else config.risk.starting_cash,
            )
        )
    return rows


def write_market_type_report_csv(rows: list[MarketTypeReportRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "market_type_report.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_type",
                "market_count",
                "traded_market_count",
                "trade_count",
                "win_rate",
                "pnl",
                "total_fees",
                "total_slippage",
                "max_drawdown",
                "ending_equity",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_type,
                    row.market_count,
                    row.traded_market_count,
                    row.trade_count,
                    row.win_rate,
                    row.pnl,
                    row.total_fees,
                    row.total_slippage,
                    row.max_drawdown,
                    row.ending_equity,
                ]
            )
    return path


def print_market_type_report(rows: list[MarketTypeReportRow], path: Path) -> None:
    if not rows:
        print(f"market_type_report | rows=0 | {path}")
        return
    best = max(rows, key=lambda row: row.pnl)
    most_active = max(rows, key=lambda row: row.trade_count)
    print(
        f"market_type_report | rows={len(rows)} | "
        f"best={best.market_type} pnl={best.pnl:.2f} trades={best.trade_count} | "
        f"most_active={most_active.market_type} trades={most_active.trade_count} pnl={most_active.pnl:.2f} | {path}"
    )
