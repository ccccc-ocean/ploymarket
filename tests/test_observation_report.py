import csv
import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.observation_report import build_observation_report


class ObservationReportTests(unittest.TestCase):
    def test_scores_observed_market_types_without_promoting_negative_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            self._write_paper_run(output_dir, "range_bucket", 55, 0.015)
            self._write_backtest_summary(output_dir, "range_bucket", 8, -12.5, 0.08)

            rows = build_observation_report(directory)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].market_type, "range_bucket")
            self.assertEqual(rows[0].observed_rows, 55)
            self.assertEqual(rows[0].positive_edge_count, 55)
            self.assertEqual(rows[0].status, "blocked_research")

    def test_marks_positive_observed_type_as_promotion_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            self._write_paper_run(output_dir, "expiry_target", 60, 0.02)
            self._write_backtest_summary(output_dir, "expiry_target", 6, 8.0, 0.04)

            rows = build_observation_report(directory)

            self.assertEqual(rows[0].status, "promotion_candidate")

    def _write_paper_run(self, output_dir: Path, market_type: str, rows: int, net_edge: float) -> None:
        with (output_dir / "paper_run_123.csv").open("w", newline="", encoding="utf-8") as file:
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
            for index in range(rows):
                writer.writerow(
                    [
                        123,
                        f"m{index}",
                        market_type,
                        "Q",
                        0.5,
                        0.07,
                        "HOLD",
                        0,
                        net_edge + 0.01,
                        net_edge,
                        "observe",
                        "SKIP",
                        "",
                        "",
                        0,
                        "skip",
                    ]
                )

    def _write_backtest_summary(self, output_dir: Path, market_type: str, trades: int, pnl: float, max_drawdown: float) -> None:
        with (output_dir / "backtest_summary_by_type.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "market_type",
                    "market_count",
                    "traded_market_count",
                    "trade_count",
                    "win_rate",
                    "pnl",
                    "total_fees",
                    "total_slippage",
                    "max_drawdown",
                ]
            )
            writer.writerow([market_type, 12, 3, trades, 0.67, pnl, 2.0, 0.1, max_drawdown])
