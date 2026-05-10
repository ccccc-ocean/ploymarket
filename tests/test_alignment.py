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
                BtcCandle(0, 90.0, 110.0, 100.0, 100.0),
                BtcCandle(3600, 100.0, 120.0, 105.0, 110.0),
                BtcCandle(10800, 110.0, 130.0, 115.0, 120.0),
            ]

            rows = build_alignment_rows([market], storage, candles, [1, 3])
            summaries = summarize_alignment(rows)

            self.assertEqual(len(rows), 2)
            self.assertEqual(summaries[0].horizon_hours, 1)
            self.assertGreater(summaries[0].sample_count, 0)
