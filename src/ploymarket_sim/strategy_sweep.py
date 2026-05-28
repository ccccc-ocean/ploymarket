from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path

from .backtest import backtest_market
from .btc_price import BtcCandle
from .classifier import is_market_type
from .clob import PricePoint
from .config import AppConfig
from .portfolio import build_portfolio_curve, summarize_portfolio
from .polymarket import Market
from .storage import Storage
from .summary import aggregate_summaries, summarize_all, summarize_market


@dataclass(frozen=True)
class SweepCandidate:
    short_window: int
    long_window: int
    min_momentum: float
    min_edge: float
    btc_down_threshold: float


@dataclass(frozen=True)
class SweepResult:
    rank: int
    short_window: int
    long_window: int
    min_momentum: float
    min_edge: float
    btc_down_threshold: float
    market_count: int
    traded_market_count: int
    trade_count: int
    win_rate: float
    realized_pnl: float
    total_fees: float
    total_slippage: float
    max_drawdown: float
    event_count: int
    score: float


def default_candidates() -> list[SweepCandidate]:
    return [
        SweepCandidate(short_window, long_window, min_momentum, min_edge, -0.0025)
        for short_window, long_window in [(3, 12), (6, 24), (12, 48), (24, 96), (36, 144)]
        for min_momentum, min_edge in [
            (0.0025, 0.0015),
            (0.0050, 0.0030),
            (0.0075, 0.0050),
            (0.0100, 0.0075),
        ]
    ]


def run_strategy_sweep(
    config: AppConfig,
    storage: Storage,
    markets: list[Market],
    btc_candles: list[BtcCandle],
    market_type: str,
    limit: int,
    candidate_limit: int | None = None,
) -> list[SweepResult]:
    selected_markets = [market for market in markets if is_market_type(market, market_type)]
    histories_by_market = {
        market.id: storage.load_price_history(market.yes_token_id or "")
        for market in selected_markets
        if market.yes_token_id
    }
    candidates = default_candidates()
    if candidate_limit is not None:
        candidates = candidates[:candidate_limit]
    rows = [_evaluate_candidate(config, candidate, selected_markets, histories_by_market, btc_candles) for candidate in candidates]
    rows = sorted(rows, key=lambda row: (-row.score, -row.realized_pnl, row.max_drawdown, -row.trade_count))
    ranked = [replace(row, rank=index + 1) for index, row in enumerate(rows)]
    return ranked[:limit]


def write_strategy_sweep_csv(results: list[SweepResult], output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "strategy_sweep.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "rank",
                "short_window",
                "long_window",
                "min_momentum",
                "min_edge",
                "btc_down_threshold",
                "market_count",
                "traded_market_count",
                "trade_count",
                "win_rate",
                "realized_pnl",
                "total_fees",
                "total_slippage",
                "max_drawdown",
                "event_count",
                "score",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result.rank,
                    result.short_window,
                    result.long_window,
                    result.min_momentum,
                    result.min_edge,
                    result.btc_down_threshold,
                    result.market_count,
                    result.traded_market_count,
                    result.trade_count,
                    result.win_rate,
                    result.realized_pnl,
                    result.total_fees,
                    result.total_slippage,
                    result.max_drawdown,
                    result.event_count,
                    result.score,
                ]
            )
    return path


def print_strategy_sweep_summary(results: list[SweepResult], path: Path) -> None:
    if not results:
        print(f"strategy_sweep | candidates=0 | {path}")
        return
    best = results[0]
    print(
        "strategy_sweep | "
        f"best_rank=1 | short={best.short_window} | long={best.long_window} | "
        f"min_momentum={best.min_momentum:.4f} | min_edge={best.min_edge:.4f} | "
        f"btc_down_threshold={best.btc_down_threshold:.4f} | trades={best.trade_count} | "
        f"win_rate={best.win_rate:.1%} | pnl={best.realized_pnl:.2f} | "
        f"max_drawdown={best.max_drawdown:.1%} | score={best.score:.2f} | {path}"
    )


def _evaluate_candidate(
    config: AppConfig,
    candidate: SweepCandidate,
    markets: list[Market],
    histories_by_market: dict[str, list[PricePoint]],
    btc_candles: list[BtcCandle],
) -> SweepResult:
    candidate_config = replace(
        config,
        signal=replace(
            config.signal,
            short_window=candidate.short_window,
            long_window=candidate.long_window,
            min_momentum=candidate.min_momentum,
            min_edge=candidate.min_edge,
        ),
        btc_filter=replace(config.btc_filter, down_threshold=candidate.btc_down_threshold),
    )
    results = []
    summaries = []
    for market in markets:
        history = histories_by_market.get(market.id, [])
        if len(history) <= candidate.long_window:
            continue
        result = backtest_market(market, history, candidate_config, btc_candles)
        results.append(result)
        summaries.append(summarize_market(market, result))
    aggregate = summarize_all(summaries) if summaries else _empty_aggregate()
    portfolio_summary = summarize_portfolio(build_portfolio_curve(results, candidate_config), candidate_config)
    score = _score(aggregate.realized_pnl, portfolio_summary.max_drawdown, aggregate.trade_count)
    return SweepResult(
        rank=0,
        short_window=candidate.short_window,
        long_window=candidate.long_window,
        min_momentum=candidate.min_momentum,
        min_edge=candidate.min_edge,
        btc_down_threshold=candidate.btc_down_threshold,
        market_count=aggregate.market_count,
        traded_market_count=aggregate.traded_market_count,
        trade_count=aggregate.trade_count,
        win_rate=aggregate.win_rate,
        realized_pnl=aggregate.realized_pnl,
        total_fees=aggregate.total_fees,
        total_slippage=aggregate.total_slippage,
        max_drawdown=portfolio_summary.max_drawdown,
        event_count=portfolio_summary.event_count,
        score=score,
    )


def _score(realized_pnl: float, max_drawdown: float, trade_count: int) -> float:
    sample_penalty = max(0, 20 - trade_count) * 2.0
    drawdown_penalty = max_drawdown * 250.0
    return realized_pnl - sample_penalty - drawdown_penalty


def _empty_aggregate():
    return summarize_all([])
