import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.btc_price import BtcCandle
from ploymarket_sim.clob import PricePoint
from ploymarket_sim.config import (
    ApiConfig,
    AppConfig,
    BacktestConfig,
    BtcFilterConfig,
    BtcPriceConfig,
    CacheConfig,
    ExecutionConfig,
    RiskConfig,
    SignalConfig,
    StorageConfig,
    UniverseConfig,
)
from ploymarket_sim.polymarket import Market
from ploymarket_sim.storage import Storage
from ploymarket_sim.strategy_sweep import run_strategy_sweep


class StrategySweepTests(unittest.TestCase):
    def test_ranks_candidate_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = AppConfig(
                api=ApiConfig("", "", 1),
                cache=CacheConfig(False, ".cache/http", 60, False),
                storage=StorageConfig(True, str(Path(directory) / "test.sqlite")),
                btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "FIVE_MINUTE"),
                btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
                universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
                signal=SignalConfig("1w", 5, 36, 144, 0.005, 0.005, 0.0, 0.98, 0.02),
                execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
                risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
                backtest=BacktestConfig(10.0, 0.02, 25, directory),
            )
            storage = Storage(True, config.storage.sqlite_path)
            market = Market("m1", "Will BTC be above X?", "btc-x", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
            storage.save_markets([market])
            storage.save_price_history("yes", [PricePoint(index * 300, 0.40 + index * 0.001) for index in range(620)])
            candles = [BtcCandle(index * 300, 90.0, 110.0, 100.0, 100.0 + index * 0.01) for index in range(620)]

            results = run_strategy_sweep(config, storage, [market], candles, "price_target", 3)

            self.assertEqual([row.rank for row in results], [1, 2, 3])
            self.assertLessEqual(len(results), 3)
            self.assertTrue(all(row.long_window > row.short_window for row in results))

    def test_candidate_limit_caps_evaluated_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = AppConfig(
                api=ApiConfig("", "", 1),
                cache=CacheConfig(False, ".cache/http", 60, False),
                storage=StorageConfig(True, str(Path(directory) / "test.sqlite")),
                btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "FIVE_MINUTE"),
                btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
                universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
                signal=SignalConfig("1w", 5, 36, 144, 0.005, 0.005, 0.0, 0.98, 0.02),
                execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
                risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
                backtest=BacktestConfig(10.0, 0.02, 25, directory),
            )
            storage = Storage(True, config.storage.sqlite_path)
            market = Market("m1", "Will BTC be above X?", "btc-x", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
            storage.save_markets([market])
            storage.save_price_history("yes", [PricePoint(index * 300, 0.40 + index * 0.001) for index in range(620)])
            candles = [BtcCandle(index * 300, 90.0, 110.0, 100.0, 100.0 + index * 0.01) for index in range(620)]

            results = run_strategy_sweep(config, storage, [market], candles, "price_target", 10, candidate_limit=2)

            self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
