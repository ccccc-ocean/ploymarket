import csv
import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.strike_report import build_strike_report


class StrikeReportTests(unittest.TestCase):
    def test_groups_price_range_daily_by_strike(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backtest_summary.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        "market_id",
                        "market_type",
                        "entry_count",
                        "trade_count",
                        "win_count",
                        "loss_count",
                        "realized_pnl",
                        "total_fees",
                        "total_slippage",
                        "question",
                    ]
                )
                writer.writerow(["m1", "price_range_daily", 1, 2, 1, 0, 2.5, 0.2, 0.1, "Will Bitcoin be above $76,000?"])
                writer.writerow(["m2", "price_range_daily", 1, 2, 0, 1, -3.0, 0.3, 0.1, "Will Bitcoin be above $76,000?"])
                writer.writerow(["m3", "price_target", 1, 2, 1, 0, 9.0, 0.1, 0.1, "Will Bitcoin hit $76,000?"])

            rows = build_strike_report(path)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].strike, 76000.0)
            self.assertEqual(rows[0].trade_count, 4)
            self.assertAlmostEqual(rows[0].realized_pnl, -0.5)


if __name__ == "__main__":
    unittest.main()
