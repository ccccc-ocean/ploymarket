import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.blocked_edge_report import build_blocked_edge_report, write_blocked_edge_report_csv


class BlockedEdgeReportTests(unittest.TestCase):
    def test_groups_positive_edge_skips_by_market_and_tracks_later_takers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            self._write_run(
                output_dir / "paper_run_100.csv",
                [
                    ["100", "m1", "above_below_expiry", "Q1", "0.12", "0.02", "HOLD", "0", "0.1", "0.08", "range-like BUY_NO 价格过高，避免高价追 NO", "SKIP", "", "", "0.08", "skip"],
                    ["100", "m1", "above_below_expiry", "Q1", "0.13", "0.02", "HOLD", "0", "0.1", "0.04", "range-like BUY_NO 价格过高，避免高价追 NO", "SKIP", "", "", "0.04", "skip"],
                    ["100", "m2", "touch_below", "Q2", "0.80", "0.02", "BUY_YES", "0.4", "0.2", "0.15", "探索仓: sample", "TAKER", "BUY_YES", "0.80", "0.15", "ok"],
                ],
            )
            self._write_run(
                output_dir / "paper_run_101.csv",
                [
                    ["101", "m1", "above_below_expiry", "Q1", "0.11", "0.02", "BUY_NO", "0.4", "0.2", "0.09", "探索仓: sample", "TAKER", "BUY_NO", "0.89", "0.09", "ok"],
                ],
            )

            rows = build_blocked_edge_report(str(output_dir), recent_runs=10)
            path = write_blocked_edge_report_csv(rows, str(output_dir))

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.market_id, "m1")
            self.assertEqual(row.reason_bucket, "price_too_high_or_payout_too_low")
            self.assertEqual(row.positive_edge_skip_count, 2)
            self.assertAlmostEqual(row.max_expected_edge, 0.08)
            self.assertEqual(row.taker_count_for_market, 1)
            self.assertEqual(row.taker_sides_for_market, "BUY_NO:1")
            self.assertTrue(path.exists())

    def _write_run(self, path: Path, rows: list[list[str]]) -> None:
        path.write_text(
            "\n".join(
                [
                    "run_timestamp,market_id,market_type,question,yes_price,taker_fee_rate,action,confidence,gross_edge,net_edge,reason,execution_mode,execution_side,limit_price,expected_net_edge,execution_reason",
                    *[",".join(row) for row in rows],
                ]
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
