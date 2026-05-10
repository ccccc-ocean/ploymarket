import unittest

from ploymarket_sim.backtest import backtest_market
from ploymarket_sim.clob import PricePoint
from ploymarket_sim.config import ApiConfig, AppConfig, BacktestConfig, CacheConfig, RiskConfig, SignalConfig, UniverseConfig
from ploymarket_sim.polymarket import Market


class BacktestTests(unittest.TestCase):
    def test_entry_costs_never_push_cash_negative(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            risk=RiskConfig(10.0, 50.0, 50.0, 50.0, 1, 10.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
            backtest=BacktestConfig(10.0, 0.02, 25, "data"),
        )
        market = Market("m1", "Will BTC be above X?", "btc-x", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"])
        history = [PricePoint(i, 0.40) for i in range(4)] + [PricePoint(4 + i, 0.60) for i in range(4)]

        result = backtest_market(market, history, config)

        self.assertGreaterEqual(result.ending_cash, 0.0)
        self.assertTrue(any(trade.fee > 0 for trade in result.trades))
