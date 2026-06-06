import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.paper_sample_report import build_paper_sample_report, write_paper_sample_report_csv


class PaperSampleReportTests(unittest.TestCase):
    def test_summarizes_probe_takers_and_positive_edge_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            self._write_run(
                output_dir / "paper_run_100.csv",
                [
                    ["100", "m1", "above_below_expiry", "Q1", "0.1", "0.07", "BUY_NO", "0.2", "0.1", "0.08", "探索仓: sample", "TAKER", "BUY_NO", "0.9", "0.08", "ok"],
                    ["100", "m3", "above_below_expiry", "Q3", "0.9", "0.07", "BUY_YES", "0.2", "0.1", "0.08", "微型探索仓: 1USDC 验证超高确定性 above_below_expiry/YES v1", "TAKER", "BUY_YES", "0.9", "0.08", "ok"],
                    ["100", "m2", "range_bucket", "Q2", "0.2", "0.07", "HOLD", "0", "0.2", "0.15", "当前市场类型暂不交易，只记录观察", "SKIP", "", "", "0.15", "skip"],
                ],
            )

            rows = build_paper_sample_report(str(output_dir), recent_runs=10)
            path = write_paper_sample_report_csv(rows, str(output_dir))

            by_type = {row.market_type: row for row in rows}
            self.assertEqual(by_type["above_below_expiry"].unique_market_count, 2)
            self.assertEqual(by_type["above_below_expiry"].taker_count, 2)
            self.assertEqual(by_type["above_below_expiry"].buy_no_taker_count, 1)
            self.assertEqual(by_type["above_below_expiry"].buy_yes_taker_count, 1)
            self.assertEqual(by_type["above_below_expiry"].probe_taker_count, 2)
            self.assertIn("ultra_certainty_above_below_yes:1", by_type["above_below_expiry"].top_probe_families)
            self.assertEqual(by_type["above_below_expiry"].sample_status, "probe_only")
            self.assertEqual(by_type["range_bucket"].positive_edge_skip_count, 1)
            self.assertEqual(by_type["range_bucket"].sample_status, "sample_starved")
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
