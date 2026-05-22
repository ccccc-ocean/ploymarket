import unittest

from ploymarket_sim.btc_price import BtcCandle
from ploymarket_sim.btc_regime import blocks_directional_entry, classify_btc_regime
from ploymarket_sim.polymarket import Market
from ploymarket_sim.signals import Signal


def candle(index: int, close: float) -> BtcCandle:
    timestamp = index * 300
    return BtcCandle(timestamp, close - 5.0, close + 5.0, close, close)


def market(question: str) -> Market:
    return Market("m1", question, "btc", None, 1000, 100, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)


class BtcRegimeTests(unittest.TestCase):
    def test_classifies_uptrend(self) -> None:
        candles = [candle(index, 100.0 + index * 0.12) for index in range(40)]

        regime = classify_btc_regime(candles, candles[-1].timestamp)

        self.assertEqual(regime.label, "uptrend")

    def test_classifies_range_bound(self) -> None:
        candles = [candle(index, 100.0 + (0.05 if index % 2 else -0.05)) for index in range(40)]

        regime = classify_btc_regime(candles, candles[-1].timestamp)

        self.assertEqual(regime.label, "range_bound")

    def test_blocks_buy_no_when_above_market_is_uptrending_near_strike(self) -> None:
        candles = [candle(index, 97.0 + index * 0.08) for index in range(40)]

        blocked, reason = blocks_directional_entry(
            market("Will Bitcoin be above $100 on May 22?"),
            Signal("BUY_NO", 0.5, 0.02, 0.01, "edge"),
            candles,
            candles[-1].timestamp,
        )

        self.assertTrue(blocked)
        self.assertIn("uptrend", reason)

    def test_blocks_buy_yes_when_above_market_is_range_bound_below_strike(self) -> None:
        candles = [candle(index, 99.0 + (0.04 if index % 2 else -0.04)) for index in range(40)]

        blocked, reason = blocks_directional_entry(
            market("Will Bitcoin be above $100 on May 22?"),
            Signal("BUY_YES", 0.5, 0.02, 0.01, "edge"),
            candles,
            candles[-1].timestamp,
        )

        self.assertTrue(blocked)
        self.assertIn("range_bound", reason)

    def test_allows_buy_no_when_above_market_is_range_bound_below_strike(self) -> None:
        candles = [candle(index, 99.0 + (0.04 if index % 2 else -0.04)) for index in range(40)]

        blocked, _reason = blocks_directional_entry(
            market("Will Bitcoin be above $100 on May 22?"),
            Signal("BUY_NO", 0.5, 0.02, 0.01, "edge"),
            candles,
            candles[-1].timestamp,
        )

        self.assertFalse(blocked)


if __name__ == "__main__":
    unittest.main()
