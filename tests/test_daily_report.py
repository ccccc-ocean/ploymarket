import csv
import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.daily_report import build_daily_report


class DailyReportTests(unittest.TestCase):
    def test_builds_not_ready_report_from_csv_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self._write_csv(
                Path(directory) / "paper_report.csv",
                ["run_timestamp", "market_count", "taker_count", "maker_count", "skip_count"],
                [[1, 35, 0, 0, 35]],
            )
            self._write_csv(
                Path(directory) / "portfolio_mtm_summary.csv",
                ["realized_pnl", "max_drawdown"],
                [[10.0, 0.02]],
            )
            self._write_csv(
                Path(directory) / "backtest_summary_by_type.csv",
                ["market_type", "trade_count", "win_rate"],
                [["all", 12, 0.66]],
            )
            self._write_csv(
                Path(directory) / "alignment_summary.csv",
                ["horizon_hours", "sample_count"],
                [[1, 100]],
            )

            report = build_daily_report(directory)

            self.assertEqual(report.readiness, "not_ready")
            self.assertEqual(report.replay_trade_count, 12)

    def _write_csv(self, path: Path, header: list[str], rows: list[list[object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(header)
            writer.writerows(rows)
