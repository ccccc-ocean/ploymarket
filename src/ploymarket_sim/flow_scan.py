from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .btc_price import BtcCandle
from .classifier import classify_market
from .config import AppConfig
from .http import HttpError, get_json
from .market_rules import describe_strike_risk, infer_strike_direction, strike_distance_pct
from .polymarket import Market


@dataclass(frozen=True)
class TradeFlow:
    proxy_wallet: str
    side: str
    outcome: str
    size: float
    price: float
    timestamp: int

    @property
    def notional(self) -> float:
        return self.size * self.price


@dataclass(frozen=True)
class MarketFlowRow:
    market_id: str
    condition_id: str
    market_type: str
    question: str
    strike_direction: str
    strike_distance_pct: float | None
    strike_risk: str
    trade_count: int
    unique_wallets: int
    large_trade_count: int
    buy_yes_usdc: float
    sell_yes_usdc: float
    buy_no_usdc: float
    sell_no_usdc: float
    net_yes_usdc: float
    net_no_usdc: float
    top_wallet: str
    top_wallet_usdc: float
    flow_signal: str


def scan_market_flows(
    config: AppConfig,
    markets: list[Market],
    btc_candles: list[BtcCandle],
    limit_per_market: int = 250,
    large_trade_usdc: float = 500.0,
) -> list[MarketFlowRow]:
    latest_btc = btc_candles[-1].close if btc_candles else None
    rows = []
    for market in markets:
        if not market.condition_id:
            rows.append(_empty_row(market, latest_btc, "missing_condition_id"))
            continue
        try:
            trades = fetch_market_trades(config, market.condition_id, limit_per_market)
        except HttpError:
            rows.append(_empty_row(market, latest_btc, "trade_api_error"))
            continue
        rows.append(summarize_market_flow(market, trades, latest_btc, large_trade_usdc))
    return rows


def fetch_market_trades(config: AppConfig, condition_id: str, limit: int = 250) -> list[TradeFlow]:
    payload = get_json(
        config.api.data_base_url,
        "/trades",
        {"market": condition_id, "limit": limit, "takerOnly": "true"},
        timeout=config.api.request_timeout_seconds,
    )
    if not isinstance(payload, list):
        return []
    trades = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        trade = _parse_trade(item)
        if trade is not None:
            trades.append(trade)
    return trades


def summarize_market_flow(
    market: Market,
    trades: list[TradeFlow],
    latest_btc_price: float | None,
    large_trade_usdc: float = 500.0,
) -> MarketFlowRow:
    buy_yes = _notional(trades, "BUY", "YES")
    sell_yes = _notional(trades, "SELL", "YES")
    buy_no = _notional(trades, "BUY", "NO")
    sell_no = _notional(trades, "SELL", "NO")
    wallet_totals: dict[str, float] = {}
    for trade in trades:
        if trade.proxy_wallet:
            wallet_totals[trade.proxy_wallet] = wallet_totals.get(trade.proxy_wallet, 0.0) + trade.notional
    top_wallet, top_wallet_usdc = _top_wallet(wallet_totals)
    net_yes = buy_yes - sell_yes
    net_no = buy_no - sell_no
    flow_signal = _flow_signal(net_yes, net_no, trades)
    return MarketFlowRow(
        market_id=market.id,
        condition_id=market.condition_id or "",
        market_type=classify_market(market).market_type,
        question=market.question,
        strike_direction=infer_strike_direction(market.question),
        strike_distance_pct=strike_distance_pct(market.question, latest_btc_price),
        strike_risk=describe_strike_risk(market.question, latest_btc_price),
        trade_count=len(trades),
        unique_wallets=len(wallet_totals),
        large_trade_count=len([trade for trade in trades if trade.notional >= large_trade_usdc]),
        buy_yes_usdc=buy_yes,
        sell_yes_usdc=sell_yes,
        buy_no_usdc=buy_no,
        sell_no_usdc=sell_no,
        net_yes_usdc=net_yes,
        net_no_usdc=net_no,
        top_wallet=top_wallet,
        top_wallet_usdc=top_wallet_usdc,
        flow_signal=flow_signal,
    )


def write_flow_scan_csv(rows: list[MarketFlowRow], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "flow_scan.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "market_id",
                "condition_id",
                "market_type",
                "question",
                "strike_direction",
                "strike_distance_pct",
                "strike_risk",
                "trade_count",
                "unique_wallets",
                "large_trade_count",
                "buy_yes_usdc",
                "sell_yes_usdc",
                "buy_no_usdc",
                "sell_no_usdc",
                "net_yes_usdc",
                "net_no_usdc",
                "top_wallet",
                "top_wallet_usdc",
                "flow_signal",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.market_id,
                    row.condition_id,
                    row.market_type,
                    row.question,
                    row.strike_direction,
                    "" if row.strike_distance_pct is None else row.strike_distance_pct,
                    row.strike_risk,
                    row.trade_count,
                    row.unique_wallets,
                    row.large_trade_count,
                    row.buy_yes_usdc,
                    row.sell_yes_usdc,
                    row.buy_no_usdc,
                    row.sell_no_usdc,
                    row.net_yes_usdc,
                    row.net_no_usdc,
                    row.top_wallet,
                    row.top_wallet_usdc,
                    row.flow_signal,
                ]
            )
    return path


def print_flow_scan_summary(rows: list[MarketFlowRow], path: Path) -> None:
    active = [row for row in rows if row.trade_count > 0]
    if not active:
        print(f"flow_scan | rows={len(rows)} | active=0 | {path}")
        return
    yes_pressure = len([row for row in active if row.flow_signal == "YES_PRESSURE"])
    no_pressure = len([row for row in active if row.flow_signal == "NO_PRESSURE"])
    large_trades = sum(row.large_trade_count for row in active)
    far_risk = len([row for row in active if row.strike_risk in {"far_above_spot", "far_below_spot"}])
    strongest = max(active, key=lambda row: abs(row.net_yes_usdc - row.net_no_usdc))
    print(
        "flow_scan | "
        f"rows={len(rows)} | active={len(active)} | yes_pressure={yes_pressure} | "
        f"no_pressure={no_pressure} | large_trades={large_trades} | far_risk={far_risk} | "
        f"strongest={strongest.market_id} {strongest.flow_signal} | {path}"
    )


def _parse_trade(item: dict[str, Any]) -> TradeFlow | None:
    try:
        return TradeFlow(
            proxy_wallet=str(item.get("proxyWallet") or ""),
            side=str(item.get("side") or "").upper(),
            outcome=str(item.get("outcome") or "").upper(),
            size=float(item.get("size") or 0.0),
            price=float(item.get("price") or 0.0),
            timestamp=int(item.get("timestamp") or 0),
        )
    except (TypeError, ValueError):
        return None


def _empty_row(market: Market, latest_btc_price: float | None, signal: str) -> MarketFlowRow:
    return MarketFlowRow(
        market_id=market.id,
        condition_id=market.condition_id or "",
        market_type=classify_market(market).market_type,
        question=market.question,
        strike_direction=infer_strike_direction(market.question),
        strike_distance_pct=strike_distance_pct(market.question, latest_btc_price),
        strike_risk=describe_strike_risk(market.question, latest_btc_price),
        trade_count=0,
        unique_wallets=0,
        large_trade_count=0,
        buy_yes_usdc=0.0,
        sell_yes_usdc=0.0,
        buy_no_usdc=0.0,
        sell_no_usdc=0.0,
        net_yes_usdc=0.0,
        net_no_usdc=0.0,
        top_wallet="",
        top_wallet_usdc=0.0,
        flow_signal=signal,
    )


def _notional(trades: list[TradeFlow], side: str, outcome: str) -> float:
    return sum(trade.notional for trade in trades if trade.side == side and trade.outcome == outcome)


def _top_wallet(wallet_totals: dict[str, float]) -> tuple[str, float]:
    if not wallet_totals:
        return "", 0.0
    wallet = max(wallet_totals, key=wallet_totals.get)
    return wallet, wallet_totals[wallet]


def _flow_signal(net_yes: float, net_no: float, trades: list[TradeFlow]) -> str:
    if not trades:
        return "NO_RECENT_TRADES"
    threshold = max(100.0, sum(trade.notional for trade in trades) * 0.15)
    if net_yes - net_no > threshold:
        return "YES_PRESSURE"
    if net_no - net_yes > threshold:
        return "NO_PRESSURE"
    return "MIXED"
