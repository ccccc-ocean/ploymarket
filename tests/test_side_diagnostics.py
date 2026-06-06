import csv
import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.side_diagnostics import build_side_diagnostics


class SideDiagnosticsTests(unittest.TestCase):
    def test_groups_replay_pnl_by_market_type_and_side(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            with (output_dir / "backtest_summary.csv").open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["market_id", "market_type"])
                writer.writerow(["m1", "above_below_expiry"])
            with (output_dir / "backtest_m1.csv").open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["timestamp", "market_id", "action", "price", "notional", "fee", "slippage", "pnl", "net_edge", "reason"])
                writer.writerow([1, "m1", "BUY_NO", 0.40, 25, 0.5, 0.1, 0, 0.02, "entry"])
                writer.writerow([2, "m1", "SELL_NO", 0.60, 37, 0.4, 0, 11.0, 0, "take profit"])
                writer.writerow([3, "m1", "BUY_YES", 0.70, 25, 0.3, 0.1, 0, 0.01, "entry"])
                writer.writerow([4, "m1", "SELL_YES", 0.50, 18, 0.2, 0, -7.0, 0, "stop loss"])

            rows = build_side_diagnostics(directory)

            by_side = {row.side: row for row in rows}
            self.assertEqual(by_side["NO"].realized_pnl, 11.0)
            self.assertEqual(by_side["NO"].status, "collect_more_samples")
            self.assertEqual(by_side["YES"].realized_pnl, -7.0)
            self.assertEqual(by_side["YES"].top_loss_reason, "stop loss (1)")
