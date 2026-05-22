import unittest

from ploymarket_sim.backtest import backtest_market
from ploymarket_sim.clob import PricePoint
from ploymarket_sim.btc_price import BtcCandle
from ploymarket_sim.config import ApiConfig, AppConfig, BacktestConfig, BtcFilterConfig, BtcPriceConfig, CacheConfig, ExecutionConfig, RiskConfig, SignalConfig, StorageConfig, UniverseConfig
from ploymarket_sim.polymarket import Market


class BacktestTests(unittest.TestCase):
    def test_entry_costs_never_push_cash_negative(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "ONE_HOUR"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(True, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(10.0, 50.0, 50.0, 50.0, 1, 10.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
            backtest=BacktestConfig(10.0, 0.02, 25, "data"),
        )
        market = Market("m1", "Will BTC hit $100,000?", "btc-hit-100k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [PricePoint(i, 0.40) for i in range(4)] + [PricePoint(4 + i, 0.60) for i in range(4)]

        result = backtest_market(market, history, config)

        self.assertGreaterEqual(result.ending_cash, 0.0)
        self.assertTrue(any(trade.fee > 0 for trade in result.trades))

    def test_maker_order_only_fills_when_price_reaches_limit(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "ONE_HOUR"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.05, 0.02, 0.98, 0.02),
            execution=ExecutionConfig(True, 0.05, 0.015, 0.0, 7200),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
            backtest=BacktestConfig(10.0, 0.02, 25, "data"),
        )
        market = Market("m1", "Will BTC hit $100,000?", "btc-hit-100k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [
            PricePoint(1, 0.50),
            PricePoint(2, 0.50),
            PricePoint(3, 0.52),
            PricePoint(4, 0.58),
            PricePoint(5, 0.60),
            PricePoint(6, 0.54),
            PricePoint(7, 0.70),
        ]

        result = backtest_market(market, history, config)

        self.assertTrue(any(trade.action == "MAKER_BUY_YES" for trade in result.trades))
        self.assertTrue(any(event.status == "matched" for event in result.order_events))

    def test_btc_filter_blocks_high_yes_after_btc_weakness(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "ONE_HOUR"),
            btc_filter=BtcFilterConfig(True, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
            backtest=BacktestConfig(10.0, 0.02, 25, "data"),
        )
        market = Market("m1", "Will BTC hit $100,000?", "btc-hit-100k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [PricePoint(i * 3600, 0.55 + i * 0.03) for i in range(8)]
        btc_candles = [
            BtcCandle(i * 3600, 80.0, 110.0, 100.0 - i, 100.0 - i)
            for i in range(8)
        ]

        result = backtest_market(market, history, config, btc_candles)

        self.assertEqual(result.trades, [])

    def test_btc_weakness_filter_does_not_block_buy_no(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "ONE_HOUR"),
            btc_filter=BtcFilterConfig(True, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
            backtest=BacktestConfig(10.0, 0.02, 25, "data"),
        )
        market = Market("m1", "Will Bitcoin be above $100 on May 22?", "btc-above-100", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [PricePoint(i * 3600, 0.70 - i * 0.03) for i in range(8)]
        btc_candles = [
            BtcCandle(i * 3600, 80.0, 110.0, 100.0 - i, 100.0 - i)
            for i in range(8)
        ]

        result = backtest_market(market, history, config, btc_candles)

        self.assertTrue(any(trade.action == "BUY_NO" for trade in result.trades))
