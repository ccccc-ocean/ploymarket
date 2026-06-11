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
        market = Market("m1", "Bitcoin Up or Down on May 22?", "btc-up-down", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [PricePoint(i, 0.40) for i in range(4)] + [PricePoint(4 + i, 0.60) for i in range(4)]
        btc_candles = [BtcCandle(i, 98500.0, 99000.0, 98500.0, 98500.0) for i in range(len(history))]

        result = backtest_market(market, history, config, btc_candles)

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

    def test_far_price_target_reach_is_rejected_by_spot_distance(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "FIVE_MINUTE"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
            backtest=BacktestConfig(10.0, 0.0, 0, "data"),
        )
        market = Market("m1", "Will Bitcoin reach $80,000 May 18-24?", "btc-reach-80k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [PricePoint(i * 300, price) for i, price in enumerate([0.50, 0.50, 0.52, 0.58, 0.60])]
        btc_candles = [BtcCandle(i * 300, 75000.0, 76000.0, 75500.0, 75500.0) for i in range(5)]

        result = backtest_market(market, history, config, btc_candles)

        # Critical #1 lets the signal layer emit BUY_YES on target-like markets;
        # the market_rules distance gate is now the sole rejection point.
        self.assertFalse(any(trade.action == "BUY_YES" for trade in result.trades))
        self.assertTrue(
            any(trade.action == "REJECTED" and "距离过远" in trade.reason for trade in result.trades)
        )

    def test_near_price_target_dip_buy_yes_is_observe_only(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "FIVE_MINUTE"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
            backtest=BacktestConfig(10.0, 0.0, 0, "data"),
        )
        market = Market("m1", "Will Bitcoin dip to $74,000 May 18-24?", "btc-dip-74k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        # Critical #1 enables BUY_YES on target-like markets when momentum/edge
        # clear the ×3 multipliers. Keep the "observe only" intent by giving a
        # mild uptrend that fails the tightened thresholds rather than relying
        # on the signal layer's old blanket block.
        history = [PricePoint(i * 300, price) for i, price in enumerate([0.50, 0.50, 0.51, 0.52, 0.53])]
        btc_candles = [BtcCandle(i * 300, 75400.0, 75800.0, 75600.0, 75600.0) for i in range(5)]

        result = backtest_market(market, history, config, btc_candles)

        self.assertFalse(any(trade.action == "BUY_YES" for trade in result.trades))

    def test_price_target_buy_yes_stop_loss_path_uses_target_cooldown(self) -> None:
        # Critical #1 re-enables BUY_YES on target-like markets. This test now
        # pins the full lifecycle: BUY_YES opens with strong momentum, then a
        # sharp drawdown triggers SELL_YES via stop loss and the target-specific
        # cooldown keeps the same market off-limits.
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "FIVE_MINUTE"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.10, 0.9, 1.0, 0.01, 0.99, target_stop_cooldown_seconds=3600),
            backtest=BacktestConfig(10.0, 0.0, 0, "data"),
        )
        market = Market("m1", "Will Bitcoin reach $80,000 May 18-24?", "btc-reach-80k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        prices = [0.50, 0.50, 0.52, 0.58, 0.60, 0.48, 0.50, 0.54, 0.60, 0.66]
        history = [PricePoint(i * 300, price) for i, price in enumerate(prices)]
        btc_candles = [BtcCandle(i * 300, 79000.0, 79500.0, 79200.0, 79200.0) for i in range(len(prices))]

        result = backtest_market(market, history, config, btc_candles)

        self.assertTrue(any(trade.action == "BUY_YES" for trade in result.trades))
        self.assertTrue(
            any(trade.action == "SELL_YES" and "止损" in trade.reason for trade in result.trades)
        )

    def test_price_range_stop_loss_sets_market_reentry_cooldown(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "ONE_HOUR"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.10, 0.9, 1.0, 0.01, 0.99, paper_reentry_cooldown_seconds=3600),
            backtest=BacktestConfig(10.0, 0.0, 0, "data"),
        )
        market = Market("m1", "Will Bitcoin be above $100 on May 22?", "btc-above-100", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        prices = [0.60, 0.60, 0.58, 0.50, 0.45, 0.60, 0.58, 0.50, 0.45, 0.40]
        history = [PricePoint(i * 300, price) for i, price in enumerate(prices)]
        btc_closes = [100.0, 99.8, 99.7, 99.5, 99.3, 99.2, 99.1, 99.0, 98.9, 98.8]
        btc_candles = [BtcCandle(i * 300, close, close + 0.1, close - 0.1, close) for i, close in enumerate(btc_closes)]

        result = backtest_market(market, history, config, btc_candles)

        self.assertTrue(any(trade.action == "SELL_NO" and "止损" in trade.reason for trade in result.trades))
        self.assertTrue(any(trade.action == "REJECTED" and "冷却中" in trade.reason for trade in result.trades))

    def test_far_price_target_reach_can_buy_no(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "FIVE_MINUTE"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
            backtest=BacktestConfig(10.0, 0.0, 0, "data"),
        )
        market = Market("m1", "Will Bitcoin reach $80,000 May 18-24?", "btc-reach-80k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [PricePoint(i * 300, price) for i, price in enumerate([0.60, 0.60, 0.58, 0.50, 0.45])]
        btc_candles = [BtcCandle(i * 300, 75000.0, 76000.0, 75500.0, 75500.0) for i in range(5)]

        result = backtest_market(market, history, config, btc_candles)

        self.assertTrue(any(trade.action == "BUY_NO" for trade in result.trades))

    def test_near_price_target_reach_blocks_buy_no(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "FIVE_MINUTE"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99),
            backtest=BacktestConfig(10.0, 0.0, 0, "data"),
        )
        market = Market("m1", "Will Bitcoin reach $80,000 May 18-24?", "btc-reach-80k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [PricePoint(i * 300, price) for i, price in enumerate([0.60, 0.60, 0.58, 0.50, 0.45])]
        btc_candles = [BtcCandle(i * 300, 79000.0, 79500.0, 79000.0, 79000.0) for i in range(5)]

        result = backtest_market(market, history, config, btc_candles)

        self.assertFalse(any(trade.action == "BUY_NO" for trade in result.trades))
        self.assertTrue(any("暂停 BUY_NO" in trade.reason for trade in result.trades))

    def test_price_target_buy_no_rejects_poor_reward_price(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "FIVE_MINUTE"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99, target_buy_no_max_price=0.75),
            backtest=BacktestConfig(10.0, 0.0, 0, "data"),
        )
        market = Market("m1", "Will Bitcoin dip to $74,000 May 18-24?", "btc-dip-74k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [PricePoint(i * 300, price) for i, price in enumerate([0.35, 0.35, 0.32, 0.25, 0.20])]
        btc_candles = [BtcCandle(i * 300, 77500.0, 78000.0, 77500.0, 77500.0) for i in range(5)]

        result = backtest_market(market, history, config, btc_candles)

        self.assertFalse(any(trade.action == "BUY_NO" for trade in result.trades))
        self.assertEqual(result.trades, [])

    def test_price_target_buy_yes_rejects_poor_reward_price(self) -> None:
        config = AppConfig(
            api=ApiConfig("", "", 1),
            cache=CacheConfig(False, ".cache/http", 60, False),
            storage=StorageConfig(False, "unused.sqlite"),
            btc_price=BtcPriceConfig("coinbase_public", "https://api.coinbase.com", "BTC-USD", "FIVE_MINUTE"),
            btc_filter=BtcFilterConfig(False, 1, -0.0025, 0.50),
            universe=UniverseConfig(["btc"], 1, 1, "volume", True, False, 0.0, True),
            signal=SignalConfig("1w", 60, 2, 4, 0.01, 0.01, 0.0, 0.98, 0.02),
            execution=ExecutionConfig(False, 0.01, 0.015, 0.0, 300),
            risk=RiskConfig(100.0, 50.0, 50.0, 50.0, 1, 100.0, 1.0, 0.9, 0.9, 1.0, 0.01, 0.99, target_buy_yes_max_price=0.65),
            backtest=BacktestConfig(10.0, 0.0, 0, "data"),
        )
        market = Market("m1", "Will Bitcoin dip to $74,000 May 18-24?", "btc-dip-74k", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        history = [PricePoint(i * 300, price) for i, price in enumerate([0.55, 0.55, 0.58, 0.62, 0.70])]
        btc_candles = [BtcCandle(i * 300, 74400.0, 74700.0, 74500.0, 74500.0) for i in range(5)]

        result = backtest_market(market, history, config, btc_candles)

        # Critical #1 lets the signal layer emit BUY_YES; market_rules' price
        # cap is now the rejection point and surfaces a REJECTED row.
        self.assertFalse(any(trade.action == "BUY_YES" for trade in result.trades))
        self.assertTrue(
            any(trade.action == "REJECTED" and "价格过高" in trade.reason for trade in result.trades)
        )
