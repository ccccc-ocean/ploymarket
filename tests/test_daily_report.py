import csv
import tempfile
import unittest
from pathlib import Path
from time import time

from ploymarket_sim.daily_report import build_daily_report
from ploymarket_sim.pipeline_health import mark_finished, mark_started


class DailyReportTests(unittest.TestCase):
    def test_builds_not_ready_report_from_csv_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self._write_healthy_live_state(directory)
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

    def test_latest_empty_paper_run_blocks_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self._write_healthy_live_state(directory)
            self._write_csv(
                Path(directory) / "paper_report.csv",
                ["run_timestamp", "market_count", "taker_count", "maker_count", "skip_count"],
                [[1, 35, 0, 0, 35], [2, 0, 0, 0, 0]],
            )
            self._write_csv(
                Path(directory) / "portfolio_mtm_summary.csv",
                ["realized_pnl", "max_drawdown"],
                [[100.0, 0.02]],
            )
            self._write_csv(
                Path(directory) / "backtest_summary_by_type.csv",
                ["market_type", "trade_count", "win_rate"],
                [["all", 100, 0.66]],
            )
            self._write_csv(
                Path(directory) / "alignment_summary.csv",
                ["horizon_hours", "sample_count"],
                [[1, 20000]],
            )

            report = build_daily_report(directory)

            self.assertEqual(report.readiness, "not_ready")
            self.assertIn("没有实时市场数据", report.reason)

    def test_failed_live_pipeline_blocks_candidate_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mark_started(Path(directory) / "health", "live_paper_cycle", "failed-run", 1)
            mark_finished(Path(directory) / "health", "live_paper_cycle", "failed-run", 2, 1, "paper-run")
            self._write_csv(
                Path(directory) / "paper_report.csv",
                ["run_timestamp", "market_count", "taker_count", "maker_count", "skip_count"],
                [[1, 35, 0, 0, 35]] * 14,
            )
            self._write_csv(
                Path(directory) / "portfolio_mtm_summary.csv",
                ["realized_pnl", "max_drawdown"],
                [[100.0, 0.02]],
            )
            self._write_csv(
                Path(directory) / "backtest_summary_by_type.csv",
                ["market_type", "trade_count", "win_rate"],
                [["all", 100, 0.66]],
            )
            self._write_csv(
                Path(directory) / "alignment_summary.csv",
                ["horizon_hours", "sample_count"],
                [[1, 20000]],
            )

            report = build_daily_report(directory)

            self.assertEqual(report.readiness, "not_ready")
            self.assertFalse(report.live_pipeline_healthy)
            self.assertIn("failed_at_paper-run", report.reason)

    def test_configurable_readiness_drawdown_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self._write_healthy_live_state(directory)
            self._write_csv(
                Path(directory) / "paper_report.csv",
                ["run_timestamp", "market_count", "taker_count", "maker_count", "skip_count"],
                [[index, 35, 0, 0, 35] for index in range(14)],
            )
            self._write_csv(
                Path(directory) / "portfolio_mtm_summary.csv",
                ["realized_pnl", "max_drawdown"],
                [[100.0, 0.09]],
            )
            self._write_csv(
                Path(directory) / "backtest_summary_by_type.csv",
                ["market_type", "trade_count", "win_rate"],
                [["all", 100, 0.66]],
            )
            self._write_csv(
                Path(directory) / "alignment_summary.csv",
                ["horizon_hours", "sample_count"],
                [[1, 20000]],
            )

            strict_report = build_daily_report(directory)
            observed_report = build_daily_report(directory, readiness_max_drawdown_pct=0.10)

            self.assertEqual(strict_report.readiness, "not_ready")
            self.assertEqual(observed_report.readiness, "candidate")

    def _write_healthy_live_state(self, directory: str) -> None:
        now = int(time())
        mark_started(Path(directory) / "health", "live_paper_cycle", "ok", now)
        mark_finished(Path(directory) / "health", "live_paper_cycle", "ok", now, 0, "flow-scan")

    def _write_csv(self, path: Path, header: list[str], rows: list[list[object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(header)
            writer.writerows(rows)
