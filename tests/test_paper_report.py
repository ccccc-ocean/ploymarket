import csv
import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.paper_report import load_paper_run_summaries


class PaperReportTests(unittest.TestCase):
    def test_loads_paper_run_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper_run_123.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        "run_timestamp",
                        "market_id",
                        "market_type",
                        "question",
                        "yes_price",
                        "taker_fee_rate",
                        "action",
                        "confidence",
                        "gross_edge",
                        "net_edge",
                        "reason",
                        "execution_mode",
                        "execution_side",
                        "limit_price",
                        "expected_net_edge",
                        "execution_reason",
                    ]
                )
                writer.writerow([123, "m1", "price_target", "Q1", 0.5, 0.07, "HOLD", 0, 0.01, -0.01, "wait", "SKIP", "", "", -0.01, "skip"])
                writer.writerow([123, "m2", "price_target", "Q2", 0.5, 0.07, "BUY_YES", 0.5, 0.08, 0.04, "edge", "TAKER", "BUY_YES", 0.5, 0.04, "take"])

            summaries = load_paper_run_summaries(directory)

            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0].buy_yes_count, 1)
            self.assertEqual(summaries[0].taker_count, 1)
            self.assertEqual(summaries[0].skip_count, 1)
            self.assertEqual(summaries[0].best_market_id, "m2")
