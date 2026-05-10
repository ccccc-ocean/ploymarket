import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.clob import PricePoint
from ploymarket_sim.polymarket import Market
from ploymarket_sim.storage import Storage


class StorageTests(unittest.TestCase):
    def test_saves_markets_and_price_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(True, str(Path(directory) / "test.sqlite"))
            market = Market(
                "m1",
                "Will Bitcoin reach $100,000 in May?",
                "btc-100k",
                None,
                1000,
                100,
                True,
                ["Yes", "No"],
                [0.5, 0.5],
                ["yes-token", "no-token"],
                True,
                0.07,
                "crypto_fees",
            )

            storage.save_markets([market])
            storage.save_price_history("yes-token", [PricePoint(1, 0.5), PricePoint(2, 0.6)])
            stats = storage.stats()

            self.assertEqual(stats.market_count, 1)
            self.assertEqual(stats.price_point_count, 2)
            markets = storage.load_markets()
            self.assertEqual(len(markets), 1)
            self.assertEqual(markets[0].yes_token_id, "yes-token")
            history = storage.load_price_history("yes-token")
            self.assertEqual([point.price for point in history], [0.5, 0.6])

    def test_disabled_storage_reports_zero_counts(self) -> None:
        storage = Storage(False, "unused.sqlite")

        stats = storage.stats()

        self.assertFalse(stats.enabled)
        self.assertEqual(stats.market_count, 0)
