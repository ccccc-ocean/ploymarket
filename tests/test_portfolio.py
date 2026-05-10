import unittest

from ploymarket_sim.backtest import BacktestResult, Trade
from ploymarket_sim.config import ApiConfig, AppConfig, BacktestConfig, CacheConfig, RiskConfig, SignalConfig, StorageConfig, UniverseConfig
from ploymarket_sim.clob import PricePoint
from ploymarket_sim.portfolio import build_mark_to_market_curve, build_portfolio_curve, summarize_portfolio


def app_config() -> AppConfig:
    return AppConfig(
        api=ApiConfig("", "", 1),
        cache=CacheConfig(False, ".cache/http", 60, False),
        storage=StorageConfig(False, "unused.sqlite"),
        universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
        signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
        risk=RiskConfig(1000.0, 50.0, 50.0, 100.0, 2, 50.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
        backtest=BacktestConfig(25.0, 0.02, 25, "data"),
    )


class PortfolioTests(unittest.TestCase):
    def test_builds_portfolio_curve_from_trades(self) -> None:
        config = app_config()
        result = BacktestResult(
            "m1",
            "Will Bitcoin reach $100,000 in May?",
            [
                Trade(1, "m1", "BUY_YES", 0.5, 25.0, 0.1, 0.05, 0.0, 0.04, "entry"),
                Trade(2, "m1", "MARK_TO_MARKET_EXIT", 0.6, 30.0, 0.1, 0.0, 4.75, 0.0, "exit"),
            ],
            1004.75,
            4.75,
        )

        curve = build_portfolio_curve([result], config)
        summary = summarize_portfolio(curve, config)

        self.assertEqual(len(curve), 2)
        self.assertAlmostEqual(curve[0].cash, 974.85)
        self.assertAlmostEqual(summary.ending_equity, 1004.85)
        self.assertAlmostEqual(summary.realized_pnl, 4.85)
        self.assertGreater(summary.max_drawdown, 0.0)

    def test_builds_mark_to_market_curve_from_price_history(self) -> None:
        config = app_config()
        result = BacktestResult(
            "m1",
            "Will Bitcoin reach $100,000 in May?",
            [
                Trade(1, "m1", "BUY_YES", 0.5, 25.0, 0.1, 0.05, 0.0, 0.04, "entry"),
                Trade(3, "m1", "MARK_TO_MARKET_EXIT", 0.6, 30.0, 0.1, 0.0, 4.75, 0.0, "exit"),
            ],
            1004.75,
            4.75,
        )

        curve = build_mark_to_market_curve([result], {"m1": [PricePoint(2, 0.4)]}, config)

        self.assertTrue(any(point.action == "MARK" for point in curve))
        mark = [point for point in curve if point.action == "MARK"][0]
        self.assertLess(mark.equity, 999.85)
