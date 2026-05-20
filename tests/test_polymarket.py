import unittest

from ploymarket_sim.polymarket import Market, _parse_market


class PolymarketParsingTests(unittest.TestCase):
    def test_parses_market_fee_schedule(self) -> None:
        market = _parse_market(
            {
                "id": "1",
                "question": "Will Bitcoin reach $100,000 in May?",
                "slug": "btc-100k",
                "liquidity": "1000",
                "volume24hr": "100",
                "enableOrderBook": True,
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.5","0.5"]',
                "clobTokenIds": '["yes","no"]',
                "feesEnabled": True,
                "feeType": "crypto_fees",
                "feeSchedule": {"rate": 0.04, "takerOnly": True},
            }
        )

        self.assertIsNotNone(market)
        assert market is not None
        self.assertTrue(market.fees_enabled)
        self.assertEqual(market.yes_token_id, "yes")
        self.assertEqual(market.no_token_id, "no")
        self.assertEqual(market.yes_price, 0.5)
        self.assertEqual(market.no_price, 0.5)
        self.assertEqual(market.taker_fee_rate, 0.04)
        self.assertEqual(market.effective_taker_fee_rate(0.02), 0.04)

    def test_falls_back_to_default_fee_when_market_fee_missing(self) -> None:
        market = Market("1", "Will BTC be above X?", "btc", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)

        self.assertEqual(market.effective_taker_fee_rate(0.02), 0.02)
