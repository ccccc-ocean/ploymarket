import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.btc_price import BtcCandle
from ploymarket_sim.touch_below_path_report import build_touch_below_path_report, write_touch_below_path_report_csv


class TouchBelowPathReportTests(unittest.TestCase):
    def test_classifies_falling_toward_target_and_distance_no_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            self._write_run(
                output_dir / "paper_run_100.csv",
                [
                    ["7200", "falling", "touch_below", "Will Bitcoin dip to $60000 in June?", "0.55", "0.02", "HOLD", "0", "0.05", "0.04", "净优势不足，等待更清晰的定价偏差", "SKIP", "", "", "0.04", "skip"],
                    ["7200", "safe", "touch_below", "Will Bitcoin dip to $60000 in June?", "0.55", "0.02", "HOLD", "0", "0.05", "0.04", "净优势不足，等待更清晰的定价偏差", "SKIP", "", "", "0.04", "skip"],
                ],
            )
            falling_candles = [
                BtcCandle(3600, 71000.0, 71100.0, 70900.0, 71000.0),
                BtcCandle(6300, 70700.0, 70800.0, 70600.0, 70700.0),
                BtcCandle(7200, 70300.0, 70400.0, 70200.0, 70300.0),
            ]

            rows = build_touch_below_path_report(str(output_dir), falling_candles, recent_runs=10)
            by_id = {row.market_id: row for row in rows}
            self.assertEqual(by_id["falling"].path_state, "falling_toward_target")

            stable_candles = [
                BtcCandle(3600, 70100.0, 70200.0, 70000.0, 70100.0),
                BtcCandle(6300, 70200.0, 70300.0, 70100.0, 70200.0),
                BtcCandle(7200, 70300.0, 70400.0, 70200.0, 70300.0),
            ]
            rows = build_touch_below_path_report(str(output_dir), stable_candles, recent_runs=10)
            by_id = {row.market_id: row for row in rows}
            self.assertEqual(by_id["safe"].path_state, "distance_no_probe_candidate")
            self.assertTrue(write_touch_below_path_report_csv(rows, str(output_dir)).exists())

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
