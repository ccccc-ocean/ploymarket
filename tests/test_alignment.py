import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.alignment import build_alignment_rows, summarize_alignment
from ploymarket_sim.btc_price import BtcCandle
from ploymarket_sim.clob import PricePoint
from ploymarket_sim.polymarket import Market
from ploymarket_sim.storage import Storage


class AlignmentTests(unittest.TestCase):
    def test_builds_alignment_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(True, str(Path(directory) / "test.sqlite"))
            market = Market("m1", "Will BTC be above X?", "btc", None, 1000, 100, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
            storage.save_markets([market])
            storage.save_price_history("yes", [PricePoint(100, 0.40), PricePoint(3700, 0.45), PricePoint(10900, 0.50)])
            candles = [
                BtcCandle(-10800, 80.0, 100.0, 90.0, 90.0),
                BtcCandle(-3600, 85.0, 105.0, 95.0, 95.0),
                BtcCandle(0, 90.0, 110.0, 100.0, 100.0),
                BtcCandle(3600, 100.0, 120.0, 105.0, 110.0),
                BtcCandle(10800, 110.0, 130.0, 115.0, 120.0),
            ]

            rows = build_alignment_rows([market], storage, candles, [1, 3])
            summaries = summarize_alignment(rows)

            self.assertEqual(len(rows), 2)
            self.assertGreater(rows[0].btc_past_1h_return, 0.0)
            self.assertEqual(summaries[0].horizon_hours, 1)
            self.assertGreater(summaries[0].sample_count, 0)

    def test_builds_alignment_rows_from_unsorted_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(True, str(Path(directory) / "test.sqlite"))
            market = Market("m1", "Will BTC be above X?", "btc", None, 1000, 100, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
            storage.save_markets([market])
            storage.save_price_history("yes", [PricePoint(10900, 0.50), PricePoint(100, 0.40), PricePoint(3700, 0.45)])
            candles = [
                BtcCandle(10800, 110.0, 130.0, 115.0, 120.0),
                BtcCandle(-10800, 80.0, 100.0, 90.0, 90.0),
                BtcCandle(3600, 100.0, 120.0, 105.0, 110.0),
                BtcCandle(-3600, 85.0, 105.0, 95.0, 95.0),
                BtcCandle(0, 90.0, 110.0, 100.0, 100.0),
            ]

            rows = build_alignment_rows([market], storage, candles, [1, 3])

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].timestamp, 100)
            self.assertEqual(rows[0].future_yes_price, 0.45)

    def test_can_limit_alignment_to_recent_points_per_market(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(True, str(Path(directory) / "test.sqlite"))
            market = Market("m1", "Will BTC be above X?", "btc", None, 1000, 100, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
            storage.save_markets([market])
            storage.save_price_history(
                "yes",
                [PricePoint(100, 0.40), PricePoint(3700, 0.45), PricePoint(7300, 0.47), PricePoint(10900, 0.50)],
            )
            candles = [
                BtcCandle(-10800, 80.0, 100.0, 90.0, 90.0),
                BtcCandle(-3600, 85.0, 105.0, 95.0, 95.0),
                BtcCandle(0, 90.0, 110.0, 100.0, 100.0),
                BtcCandle(3600, 100.0, 120.0, 105.0, 110.0),
                BtcCandle(7200, 105.0, 125.0, 110.0, 115.0),
                BtcCandle(10800, 110.0, 130.0, 115.0, 120.0),
                BtcCandle(14400, 115.0, 135.0, 120.0, 125.0),
            ]

            rows = build_alignment_rows([market], storage, candles, [1], max_points_per_market=2)

            self.assertEqual([row.timestamp for row in rows], [7300])
