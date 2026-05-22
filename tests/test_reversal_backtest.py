import unittest

from ploymarket_sim.clob import PricePoint
from ploymarket_sim.config import ApiConfig, AppConfig, BacktestConfig, BtcFilterConfig, BtcPriceConfig, CacheConfig, ExecutionConfig, RiskConfig, SignalConfig, StorageConfig, UniverseConfig
from ploymarket_sim.polymarket import Market
from ploymarket_sim.reversal_backtest import ReversalStrategy, run_reversal_backtest, summarize_reversal_results


def app_config() -> AppConfig:
    return AppConfig(
        api=ApiConfig("", "", 1),
        cache=CacheConfig(False, ".cache/http", 60, False),
        storage=StorageConfig(False, "unused.sqlite"),
        btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "ONE_HOUR"),
        btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
        universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
        signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.005, 0.0, 0.98, 0.02),
        execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
        risk=RiskConfig(1000.0, 50.0, 75.0, 250.0, 5, 35.0, 0.12, 0.25, 0.35, 0.08, 0.03, 0.97),
        backtest=BacktestConfig(25.0, 0.02, 25, "data"),
    )


def market() -> Market:
    return Market("m1", "Will the price of Bitcoin be above $78,000 on May 22?", "btc-above-78k", None, 1000, 100, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)


class ReversalBacktestTests(unittest.TestCase):
    def test_can_buy_no_on_negative_yes_momentum(self) -> None:
        strategy = ReversalStrategy("YES_NO", True, False, 0.25, 0.35, 0)
        history = [PricePoint(i, price) for i, price in enumerate([0.60, 0.58, 0.56, 0.54, 0.50, 0.45, 0.40, 0.35])]

        result = run_reversal_backtest(app_config(), market(), history, strategy)

        self.assertTrue(any(trade.action == "BUY_NO" for trade in result.trades))

    def test_reversal_can_enter_opposite_side_after_stop(self) -> None:
        strategy = ReversalStrategy("REV", True, True, 0.10, 0.20, 3600)
        history = [PricePoint(i, price) for i, price in enumerate([0.40, 0.42, 0.45, 0.50, 0.55, 0.43, 0.35, 0.30, 0.25])]

        result = run_reversal_backtest(app_config(), market(), history, strategy)

        actions = [trade.action for trade in result.trades]
        self.assertIn("BUY_YES", actions)
        self.assertIn("SELL_YES", actions)
        self.assertIn("BUY_NO", actions)

    def test_summarizes_reversal_results(self) -> None:
        strategy = ReversalStrategy("YES_NO", True, False, 0.25, 0.35, 0)
        history = [PricePoint(i, price) for i, price in enumerate([0.60, 0.58, 0.56, 0.54, 0.50, 0.45, 0.40, 0.35])]

        rows = summarize_reversal_results([run_reversal_backtest(app_config(), market(), history, strategy)])

        self.assertTrue(rows)
        self.assertTrue(any(row.strategy == "YES_NO" for row in rows))


if __name__ == "__main__":
    unittest.main()
