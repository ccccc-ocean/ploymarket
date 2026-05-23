import unittest

from ploymarket_sim.cross_platform import match_btc_markets
from ploymarket_sim.kalshi import KalshiMarket
from ploymarket_sim.polymarket import Market


class CrossPlatformTests(unittest.TestCase):
    def test_matches_same_btc_strike_direction_and_date(self) -> None:
        poly = Market(
            "p1",
            "Will the price of Bitcoin be above $76,000 on May 23?",
            "btc-above-76000-may-23",
            "2026-05-23T23:59:00Z",
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.45, 0.55],
            ["yes", "no"],
            False,
            None,
            None,
        )
        kalshi = KalshiMarket(
            ticker="KXBTC-26MAY23-T76000",
            event_ticker="KXBTC-26MAY23",
            title="Will Bitcoin be above $76,000 on May 23?",
            subtitle="Above $76,000",
            close_time="2026-05-23T20:00:00Z",
            status="open",
            yes_bid=0.40,
            yes_ask=0.42,
            no_bid=0.58,
            no_ask=0.60,
            last_price=None,
            volume_24h=100,
            liquidity=100,
        )

        rows = match_btc_markets([poly], [kalshi])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].match_quality, "exact")
        self.assertEqual(rows[0].cheaper_yes_platform, "kalshi")
        self.assertAlmostEqual(rows[0].yes_price_diff or 0, 0.04)


if __name__ == "__main__":
    unittest.main()
