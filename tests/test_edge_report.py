import unittest

from ploymarket_sim.alignment import AlignmentRow
from ploymarket_sim.edge_report import build_edge_buckets, btc_return_bucket, yes_price_bucket


class EdgeReportTests(unittest.TestCase):
    def test_buckets_yes_price(self) -> None:
        self.assertEqual(yes_price_bucket(0.01), "00_lt_0.03")
        self.assertEqual(yes_price_bucket(0.05), "01_0.03_0.08")
        self.assertEqual(yes_price_bucket(0.10), "02_0.08_0.20")
        self.assertEqual(yes_price_bucket(0.30), "03_0.20_0.50")
        self.assertEqual(yes_price_bucket(0.60), "04_gte_0.50")

    def test_buckets_btc_return(self) -> None:
        self.assertEqual(btc_return_bucket(-0.02), "00_btc_down_gt_1pct")
        self.assertEqual(btc_return_bucket(-0.005), "01_btc_down_0.25_1pct")
        self.assertEqual(btc_return_bucket(0.0), "02_btc_flat")
        self.assertEqual(btc_return_bucket(0.005), "03_btc_up_0.25_1pct")
        self.assertEqual(btc_return_bucket(0.02), "04_btc_up_gt_1pct")

    def test_builds_edge_buckets(self) -> None:
        rows = [
            AlignmentRow("m1", "Q", index, 1, 0.10, 0.11, 0.01, 100.0, 101.0, 0.01, 0.01, 0.02)
            for index in range(3)
        ]

        buckets = build_edge_buckets(rows, min_samples=1)

        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0].sample_count, 3)
        self.assertEqual(buckets[0].yes_up_rate, 1.0)
