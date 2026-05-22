import unittest

from ploymarket_sim.btc_price import BtcCandle
from ploymarket_sim.btc_price import merge_btc_candles
from ploymarket_sim.market_rules import blocks_btc_strike_entry, describe_strike_risk, extract_usd_strike, infer_strike_direction
from ploymarket_sim.polymarket import Market


class MarketRulesTests(unittest.TestCase):
    def test_merges_btc_candles_by_timestamp(self) -> None:
        existing = [BtcCandle(1, 1.0, 2.0, 1.5, 1.7), BtcCandle(2, 2.0, 3.0, 2.5, 2.7)]
        fresh = [BtcCandle(2, 2.0, 4.0, 3.0, 3.7), BtcCandle(3, 3.0, 4.0, 3.5, 3.7)]

        merged = merge_btc_candles(existing, fresh)

        self.assertEqual([candle.timestamp for candle in merged], [1, 2, 3])
        self.assertEqual(merged[1].high, 4.0)

    def test_extracts_usd_strike(self) -> None:
        self.assertEqual(extract_usd_strike("Will Bitcoin be above $78,000 on May 21?"), 78000.0)
        self.assertEqual(extract_usd_strike("Will Bitcoin hit $150k?"), 150000.0)

    def test_describes_far_above_and_far_below_strike_risk(self) -> None:
        self.assertEqual(infer_strike_direction("Will Bitcoin be under $60,000?"), "below")
        self.assertEqual(describe_strike_risk("Will Bitcoin be above $78,000?", 76000), "far_above_spot")
        self.assertEqual(describe_strike_risk("Will Bitcoin be under $60,000?", 78000), "far_below_spot")

    def test_blocks_above_market_when_btc_not_near_strike(self) -> None:
        market = Market("m1", "Will the price of Bitcoin be above $78,000 on May 21?", "btc-above", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        blocked, reason = blocks_btc_strike_entry(market, 300, [BtcCandle(300, 76000, 77000, 76500, 76500)])

        self.assertTrue(blocked)
        self.assertIn("above strike", reason)

    def test_allows_above_market_when_btc_near_strike(self) -> None:
        market = Market("m1", "Will the price of Bitcoin be above $78,000 on May 21?", "btc-above", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        blocked, _reason = blocks_btc_strike_entry(market, 300, [BtcCandle(300, 77700, 78000, 77880, 77900)])

        self.assertFalse(blocked)


if __name__ == "__main__":
    unittest.main()
