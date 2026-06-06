import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.probe_performance_report import build_probe_performance_report, probe_family_from_reason, write_probe_performance_report_csv
from ploymarket_sim.storage import PaperPositionState


class ProbePerformanceReportTests(unittest.TestCase):
    def test_summarizes_closed_probe_pnl_by_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            self._write_run(
                output_dir / "paper_run_100.csv",
                [
                    ["100", "m1", "above_below_expiry", "Q1", "0.2", "0.07", "BUY_NO", "0.1", "0.2", "0.1", "过滤器挑战仓: 小仓位验证被 BTC regime 拦截", "TAKER", "BUY_NO", "0.8", "0.1", "ok"],
                    ["100", "m2", "range_bucket", "Q2", "0.9", "0.07", "BUY_YES", "0.1", "0.2", "0.1", "探索仓: 连续零成交后，小仓位验证 range_bucket/YES", "TAKER", "BUY_YES", "0.9", "0.1", "ok"],
                    ["100", "m4", "touch_below", "Q4", "0.04", "0.07", "BUY_NO", "0.1", "0.04", "0.03", "探索仓: 小仓位验证高确定性 touch_below/NO v2", "TAKER", "BUY_NO", "0.96", "0.03", "ok"],
                    ["100", "m5", "above_below_expiry", "Q5", "0.92", "0.07", "BUY_YES", "0.1", "0.03", "0.02", "微型探索仓: 1USDC 验证超高确定性 above_below_expiry/YES v1", "TAKER", "BUY_YES", "0.93", "0.02", "ok"],
                    ["100", "m6", "above_below_expiry", "Q6", "0.03", "0.07", "BUY_NO", "0.1", "0.03", "0.02", "微型探索仓: 1USDC 验证超高确定性 above_below_expiry/NO v1", "TAKER", "BUY_NO", "0.97", "0.02", "ok"],
                    ["100", "m3", "touch_below", "Q3", "0.5", "0.07", "HOLD", "0", "0.1", "0.01", "净优势不足", "SKIP", "", "", "0.01", "skip"],
                ],
            )
            closed = [
                PaperPositionState("m1", "NO", 0.8, 10.0, 8.0, 100, "closed", 200, 1.5, 0, 0.9, 1),
                PaperPositionState("m4", "NO", 0.96, 3.0, 3.0, 100, "closed", 200, 0.2, 0, 0.98, 0),
                PaperPositionState("m5", "YES", 0.93, 1.0, 1.0, 100, "closed", 200, -0.1, 0, 0.93, 0),
                PaperPositionState("m6", "NO", 0.97, 1.0, 1.0, 100, "closed", 200, 0.05, 0, 0.99, 0),
            ]

            rows = build_probe_performance_report(str(output_dir), closed, {"m2"})
            path = write_probe_performance_report_csv(rows, str(output_dir))

            by_family = {row.probe_family: row for row in rows}
            self.assertEqual(by_family["regime_filter_challenge"].closed_count, 1)
            self.assertEqual(by_family["regime_filter_challenge"].realized_pnl, 1.5)
            self.assertEqual(by_family["range_bucket_yes"].open_count, 1)
            self.assertEqual(by_family["touch_below_certainty_no"].closed_count, 1)
            self.assertEqual(by_family["touch_below_certainty_no"].realized_pnl, 0.2)
            self.assertEqual(by_family["ultra_certainty_above_below_yes"].closed_count, 1)
            self.assertEqual(by_family["ultra_certainty_above_below_yes"].realized_pnl, -0.1)
            self.assertEqual(by_family["ultra_certainty_above_below_no"].closed_count, 1)
            self.assertEqual(by_family["ultra_certainty_above_below_no"].realized_pnl, 0.05)
            self.assertTrue(path.exists())

    def test_distance_touch_below_no_is_not_grouped_with_legacy_touch_below_no(self) -> None:
        family = probe_family_from_reason("微型探索仓: 1USDC 验证距离安全 touch_below/NO v1; 原因=touch_below 暂不允许 BUY_NO")

        self.assertEqual(family, "touch_below_distance_no")

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
