import unittest

from ploymarket_sim.btc_price import BtcCandle
from ploymarket_sim.btc_price import merge_btc_candles
from ploymarket_sim.market_rules import (
    blocks_btc_strike_entry,
    blocks_price_range_entry,
    blocks_price_target_entry,
    describe_strike_risk,
    extract_usd_strike,
    infer_strike_direction,
)
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

    def test_allows_buy_no_when_above_strike_is_far_away(self) -> None:
        market = Market("m1", "Will the price of Bitcoin be above $78,000 on May 21?", "btc-above", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        blocked, _reason = blocks_btc_strike_entry(market, 300, [BtcCandle(300, 76000, 77000, 76500, 76500)], "BUY_NO")

        self.assertFalse(blocked)

    def test_blocks_directional_entry_without_btc_confirmation(self) -> None:
        market = Market("m1", "Will the price of Bitcoin be above $78,000 on May 21?", "btc-above", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        blocked, reason = blocks_btc_strike_entry(market, 300, [], "BUY_NO")

        self.assertTrue(blocked)
        self.assertIn("缺少 BTC 现货确认", reason)

    def test_blocks_expensive_buy_no_in_daily_range_market(self) -> None:
        market = Market("m1", "Will the price of Bitcoin be above $74,000 on May 29?", "btc-above", None, 1000, 1000, True, ["Yes", "No"], [0.24, 0.76], ["yes", "no"], False, None, None)

        blocked, reason = blocks_price_range_entry(
            market,
            "BUY_NO",
            900,
            [BtcCandle(0, 72700, 72800, 72750, 72700), BtcCandle(900, 72750, 72900, 72800, 72850)],
            yes_price=0.24,
            buy_no_max_price=0.75,
        )

        self.assertTrue(blocked)
        self.assertIn("BUY_NO 价格过高", reason)

    def test_blocks_daily_buy_no_when_btc_moves_toward_above_strike(self) -> None:
        market = Market("m1", "Will the price of Bitcoin be above $74,000 on May 29?", "btc-above", None, 1000, 1000, True, ["Yes", "No"], [0.3, 0.7], ["yes", "no"], False, None, None)

        blocked, reason = blocks_price_range_entry(
            market,
            "BUY_NO",
            900,
            [BtcCandle(0, 72700, 72800, 72750, 72700), BtcCandle(900, 72900, 73100, 73000, 73000)],
            yes_price=0.3,
            buy_no_max_price=0.75,
            safety_band_pct=0.02,
            moving_away_return_pct=0.001,
        )

        self.assertTrue(blocked)
        self.assertIn("未明显远离 above strike", reason)

    def test_blocks_dip_target_buy_yes_when_btc_moves_away(self) -> None:
        market = Market("m1", "Will Bitcoin dip to $72,500 in May?", "btc-dip", None, 1000, 1000, True, ["Yes", "No"], [0.6, 0.4], ["yes", "no"], False, None, None)

        blocked, reason = blocks_price_target_entry(
            market,
            "BUY_YES",
            900,
            [BtcCandle(0, 73300, 73400, 73350, 73350), BtcCandle(900, 73500, 73750, 73600, 73700)],
            max_distance_pct=0.025,
            yes_price=0.6,
            moving_away_return_pct=0.001,
        )

        self.assertTrue(blocked)
        self.assertIn("正远离 below/dip target", reason)

    def test_blocks_dip_target_buy_yes_when_hourly_btc_moves_away(self) -> None:
        market = Market("m1", "Will Bitcoin dip to $72,500 in May?", "btc-dip", None, 1000, 1000, True, ["Yes", "No"], [0.6, 0.4], ["yes", "no"], False, None, None)

        blocked, reason = blocks_price_target_entry(
            market,
            "BUY_YES",
            3600,
            [
                BtcCandle(0, 72700, 72800, 72750, 72750),
                BtcCandle(2700, 73020, 73100, 73050, 73050),
                BtcCandle(3600, 73050, 73150, 73100, 73100),
            ],
            max_distance_pct=0.025,
            yes_price=0.6,
            moving_away_return_pct=0.001,
        )

        self.assertTrue(blocked)
        self.assertIn("1h 正远离 below/dip target", reason)

    def test_blocks_range_buy_no_when_hourly_btc_moves_toward_near_above_strike(self) -> None:
        market = Market("m1", "Will the price of Bitcoin be above $74,000 on May 29?", "btc-above", None, 1000, 1000, True, ["Yes", "No"], [0.4, 0.6], ["yes", "no"], False, None, None)

        blocked, reason = blocks_price_range_entry(
            market,
            "BUY_NO",
            3600,
            [
                BtcCandle(0, 73200, 73300, 73250, 73250),
                BtcCandle(2700, 73550, 73620, 73600, 73600),
                BtcCandle(3600, 73600, 73700, 73650, 73650),
            ],
            yes_price=0.4,
            buy_no_max_price=0.75,
            safety_band_pct=0.02,
            moving_away_return_pct=0.001,
        )

        self.assertTrue(blocked)
        self.assertIn("未明显远离 above strike", reason)


if __name__ == "__main__":
    unittest.main()
