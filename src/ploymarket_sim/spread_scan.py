from __future__ import annotations

from dataclasses import dataclass
import sys

from .classifier import classify_market
from .clob import TokenQuote, get_token_quote
from .config import AppConfig
from .costs import fee_amount
from .http import HttpError
from .polymarket import Market


@dataclass(frozen=True)
class SpreadScanRow:
    market_id: str
    market_type: str
    question: str
    yes_token_id: str
    no_token_id: str
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    taker_fee_rate: float
    buy_pair_cost: float | None
    buy_pair_fees: float | None
    buy_pair_slippage: float | None
    buy_pair_total_cost: float | None
    buy_pair_edge: float | None
    sell_pair_proceeds: float | None
    sell_pair_fees: float | None
    sell_pair_slippage: float | None
    sell_pair_net_proceeds: float | None
    sell_pair_edge: float | None
    recommendation: str
    reason: str


def scan_spreads(config: AppConfig, markets: list[Market]) -> list[SpreadScanRow]:
    rows = []
    for market in markets:
        row = _scan_market(config, market)
        if row is not None:
            rows.append(row)
    return rows


def print_spread_scan_summary(rows: list[SpreadScanRow], path) -> None:
    buy_both = len([row for row in rows if row.recommendation == "BUY_BOTH"])
    sell_both = len([row for row in rows if row.recommendation == "SELL_BOTH"])
    skipped = len([row for row in rows if row.recommendation == "SKIP"])
    best_buy = _max_optional(rows, lambda row: row.buy_pair_edge)
    best_sell = _max_optional(rows, lambda row: row.sell_pair_edge)
    best_buy_label = f"{best_buy.buy_pair_edge:.4f}/{best_buy.market_id}" if best_buy else "n/a"
    best_sell_label = f"{best_sell.sell_pair_edge:.4f}/{best_sell.market_id}" if best_sell else "n/a"
    print(
        f"spread_scan | markets={len(rows)} | buy_both={buy_both} | sell_both={sell_both} | "
        f"skip={skipped} | best_buy_edge={best_buy_label} | best_sell_edge={best_sell_label} | {path}"
    )


def write_spread_scan_csv(rows: list[SpreadScanRow], output_dir: str):
    import csv
    from pathlib import Path

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "spread_scan.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_id",
                "market_type",
                "question",
                "yes_token_id",
                "no_token_id",
                "yes_bid",
                "yes_ask",
                "no_bid",
                "no_ask",
                "taker_fee_rate",
                "buy_pair_cost",
                "buy_pair_fees",
                "buy_pair_slippage",
                "buy_pair_total_cost",
                "buy_pair_edge",
                "sell_pair_proceeds",
                "sell_pair_fees",
                "sell_pair_slippage",
                "sell_pair_net_proceeds",
                "sell_pair_edge",
                "recommendation",
                "reason",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_id,
                    row.market_type,
                    row.question,
                    row.yes_token_id,
                    row.no_token_id,
                    row.yes_bid,
                    row.yes_ask,
                    row.no_bid,
                    row.no_ask,
                    row.taker_fee_rate,
                    row.buy_pair_cost,
                    row.buy_pair_fees,
                    row.buy_pair_slippage,
                    row.buy_pair_total_cost,
                    row.buy_pair_edge,
                    row.sell_pair_proceeds,
                    row.sell_pair_fees,
                    row.sell_pair_slippage,
                    row.sell_pair_net_proceeds,
                    row.sell_pair_edge,
                    row.recommendation,
                    row.reason,
                ]
            )
    return path


def _scan_market(config: AppConfig, market: Market) -> SpreadScanRow | None:
    yes_token_id = market.yes_token_id
    no_token_id = market.no_token_id
    if not yes_token_id or not no_token_id:
        return _missing_row(config, market, yes_token_id or "", no_token_id or "", "missing YES/NO token id")
    try:
        yes_quote = get_token_quote(config, yes_token_id)
        no_quote = get_token_quote(config, no_token_id)
    except HttpError as exc:
        print(f"warning: skip spread scan for {market.id}: {exc}", file=sys.stderr)
        return _missing_row(config, market, yes_token_id, no_token_id, f"quote error: {exc}")
    return build_spread_scan_row(config, market, yes_quote, no_quote)


def build_spread_scan_row(
    config: AppConfig,
    market: Market,
    yes_quote: TokenQuote,
    no_quote: TokenQuote,
) -> SpreadScanRow:
    fee_rate = market.effective_taker_fee_rate(config.backtest.taker_fee_rate)
    slippage_rate = config.backtest.slippage_bps / 10_000
    buy_pair_cost = _sum_optional(yes_quote.ask, no_quote.ask)
    buy_pair_fees = None
    buy_pair_slippage = None
    buy_pair_total_cost = None
    buy_pair_edge = None
    if yes_quote.ask is not None and no_quote.ask is not None:
        buy_pair_fees = fee_amount(yes_quote.ask, yes_quote.ask, fee_rate) + fee_amount(no_quote.ask, no_quote.ask, fee_rate)
        buy_pair_slippage = buy_pair_cost * slippage_rate
        buy_pair_total_cost = buy_pair_cost + buy_pair_fees + buy_pair_slippage
        buy_pair_edge = 1.0 - buy_pair_total_cost

    sell_pair_proceeds = _sum_optional(yes_quote.bid, no_quote.bid)
    sell_pair_fees = None
    sell_pair_slippage = None
    sell_pair_net_proceeds = None
    sell_pair_edge = None
    if yes_quote.bid is not None and no_quote.bid is not None:
        sell_pair_fees = fee_amount(yes_quote.bid, yes_quote.bid, fee_rate) + fee_amount(no_quote.bid, no_quote.bid, fee_rate)
        sell_pair_slippage = sell_pair_proceeds * slippage_rate
        sell_pair_net_proceeds = sell_pair_proceeds - sell_pair_fees - sell_pair_slippage
        sell_pair_edge = sell_pair_net_proceeds - 1.0

    recommendation, reason = _recommend(buy_pair_edge, sell_pair_edge)
    return SpreadScanRow(
        market_id=market.id,
        market_type=classify_market(market).market_type,
        question=market.question,
        yes_token_id=yes_quote.token_id,
        no_token_id=no_quote.token_id,
        yes_bid=yes_quote.bid,
        yes_ask=yes_quote.ask,
        no_bid=no_quote.bid,
        no_ask=no_quote.ask,
        taker_fee_rate=fee_rate,
        buy_pair_cost=buy_pair_cost,
        buy_pair_fees=buy_pair_fees,
        buy_pair_slippage=buy_pair_slippage,
        buy_pair_total_cost=buy_pair_total_cost,
        buy_pair_edge=buy_pair_edge,
        sell_pair_proceeds=sell_pair_proceeds,
        sell_pair_fees=sell_pair_fees,
        sell_pair_slippage=sell_pair_slippage,
        sell_pair_net_proceeds=sell_pair_net_proceeds,
        sell_pair_edge=sell_pair_edge,
        recommendation=recommendation,
        reason=reason,
    )


def _recommend(buy_pair_edge: float | None, sell_pair_edge: float | None) -> tuple[str, str]:
    best_buy = buy_pair_edge if buy_pair_edge is not None else float("-inf")
    best_sell = sell_pair_edge if sell_pair_edge is not None else float("-inf")
    if best_buy > 0 and best_buy >= best_sell:
        return "BUY_BOTH", "YES ask + NO ask is below 1 after estimated fees/slippage"
    if best_sell > 0:
        return "SELL_BOTH", "YES bid + NO bid is above 1 after estimated fees/slippage"
    return "SKIP", "no positive complete-set spread after estimated fees/slippage"


def _missing_row(
    config: AppConfig,
    market: Market,
    yes_token_id: str,
    no_token_id: str,
    reason: str,
) -> SpreadScanRow:
    return SpreadScanRow(
        market_id=market.id,
        market_type=classify_market(market).market_type,
        question=market.question,
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        yes_bid=None,
        yes_ask=None,
        no_bid=None,
        no_ask=None,
        taker_fee_rate=market.effective_taker_fee_rate(config.backtest.taker_fee_rate),
        buy_pair_cost=None,
        buy_pair_fees=None,
        buy_pair_slippage=None,
        buy_pair_total_cost=None,
        buy_pair_edge=None,
        sell_pair_proceeds=None,
        sell_pair_fees=None,
        sell_pair_slippage=None,
        sell_pair_net_proceeds=None,
        sell_pair_edge=None,
        recommendation="SKIP",
        reason=reason,
    )


def _sum_optional(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left + right


def _max_optional(rows: list[SpreadScanRow], value):
    available = [row for row in rows if value(row) is not None]
    if not available:
        return None
    return max(available, key=value)
