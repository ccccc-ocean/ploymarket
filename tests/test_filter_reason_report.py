import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.filter_reason_report import build_filter_reason_report, write_filter_reason_report_csv


class FilterReasonReportTests(unittest.TestCase):
    def test_groups_skip_reasons_and_positive_edge_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            self._write_run(
                output_dir / "paper_run_100.csv",
                [
                    ["100", "m1", "touch_below", "Q1", "0.8", "0.07", "HOLD", "0", "0.2", "0.12", "price_target BUY_YES 价格过高，盈亏比不足", "SKIP", "", "", "0.12", "skip"],
                    ["100", "m2", "touch_below", "Q2", "0.7", "0.07", "HOLD", "0", "0.1", "-0.01", "净优势不足，等待更清晰的定价偏差", "SKIP", "", "", "-0.01", "skip"],
                    ["100", "m4", "above_below_expiry", "Q4", "0.7", "0.07", "HOLD", "0", "0.1", "0", "同一市场冷却中，cooldown_until=123", "SKIP", "", "", "0", "skip"],
                    ["100", "m5", "above_below_expiry", "Q5", "0.7", "0.07", "HOLD", "0", "0.1", "0", "BTC 未明显远离 above strike，暂停 BUY_NO", "SKIP", "", "", "0", "skip"],
                    ["100", "m6", "touch_above", "Q6", "0.7", "0.07", "HOLD", "0", "0.1", "0.01", "实时 ask 重定价后净 edge 不足，跳过模拟开仓: ask=0.570; required=0.0400", "SKIP", "", "", "0.01", "skip"],
                    ["100", "m3", "range_bucket", "Q3", "0.9", "0.07", "BUY_YES", "0.1", "0.2", "0.1", "探索仓", "TAKER", "BUY_YES", "0.9", "0.1", "ok"],
                ],
            )

            rows = build_filter_reason_report(str(output_dir), recent_runs=10)
            path = write_filter_reason_report_csv(rows, str(output_dir))

            by_key = {(row.market_type, row.reason_bucket): row for row in rows}
            self.assertEqual(by_key[("touch_below", "price_too_high_or_payout_too_low")].positive_edge_count, 1)
            self.assertEqual(by_key[("touch_below", "edge_too_low")].row_count, 1)
            self.assertEqual(by_key[("above_below_expiry", "loss_cooldown")].row_count, 1)
            self.assertEqual(by_key[("above_below_expiry", "btc_near_or_crossing_strike")].row_count, 1)
            self.assertEqual(by_key[("touch_above", "live_reprice_edge_too_weak")].positive_edge_count, 1)
            self.assertNotIn(("range_bucket", "other"), by_key)
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
