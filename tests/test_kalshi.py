import unittest
from unittest.mock import patch

from ploymarket_sim.config import load_config
from ploymarket_sim.kalshi import discover_kalshi_btc_markets


class KalshiTests(unittest.TestCase):
    def test_discovers_btc_markets_from_public_markets_response(self) -> None:
        payload = {
            "markets": [
                {
                    "ticker": "KXBTC-26MAY23-T76000",
                    "event_ticker": "KXBTC-26MAY23",
                    "title": "Will Bitcoin be above $76,000 on May 23?",
                    "yes_sub_title": "Above $76,000",
                    "close_time": "2026-05-23T20:00:00Z",
                    "status": "open",
                    "yes_bid_dollars": "0.4200",
                    "yes_ask_dollars": "0.4400",
                    "no_bid_dollars": "0.5600",
                    "no_ask_dollars": "0.5800",
                    "volume_24h_fp": "123.00",
                },
                {"ticker": "KXWEATHER", "title": "Will it rain?"},
            ],
            "cursor": "",
        }

        with patch("ploymarket_sim.kalshi.get_json", return_value=payload):
            markets = discover_kalshi_btc_markets(load_config("config/default.toml"), use_cache=False)

        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].ticker, "KXBTC-26MAY23-T76000")
        self.assertAlmostEqual(markets[0].mid_yes_price or 0, 0.43)


if __name__ == "__main__":
    unittest.main()
