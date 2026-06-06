import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.strategy_review import build_strategy_review, write_strategy_review_csv


class StrategyReviewTests(unittest.TestCase):
    def test_flags_positive_edge_blocked_market_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            rows = [
                ["100", f"m{i}", "touch_below", "Q", "0.2", "0.07", "HOLD", "0", "0.1", "0.06", "暂不允许 BUY_YES", "SKIP", "", "", "0.06", "skip"]
                for i in range(20)
            ]
            self._write_run(output_dir / "paper_run_100.csv", rows)

            review = build_strategy_review(str(output_dir), recent_runs=10)

            by_type = {row.market_type: row for row in review}
            self.assertEqual(by_type["touch_below"].status, "positive_edge_blocked")
            self.assertEqual(
                by_type["touch_below"].recommended_action,
                "design_touch_below_probe_with_strict_price_and_btc_confirmation",
            )

    def test_marks_probe_active_without_calling_it_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            self._write_run(
                output_dir / "paper_run_100.csv",
                [
                    ["100", "m1", "range_bucket", "Q", "0.98", "0.07", "BUY_YES", "0.1", "0.2", "0.1", "探索仓: sample", "TAKER", "BUY_YES", "0.99", "0.1", "ok"],
                ],
            )

            review = build_strategy_review(str(output_dir), recent_runs=10)
            path = write_strategy_review_csv(review, str(output_dir))

            by_type = {row.market_type: row for row in review}
            self.assertEqual(by_type["range_bucket"].status, "probe_active")
            self.assertTrue(path.exists())

    def test_edge_too_low_is_not_called_positive_edge_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            rows = [
                ["100", f"m{i}", "touch_below", "Q", "0.2", "0.07", "HOLD", "0", "0.1", "0.02", "净优势不足，等待更清晰的定价偏差", "SKIP", "", "", "0.02", "skip"]
                for i in range(20)
            ]
            self._write_run(output_dir / "paper_run_100.csv", rows)

            review = build_strategy_review(str(output_dir), recent_runs=10)

            by_type = {row.market_type: row for row in review}
            self.assertEqual(by_type["touch_below"].status, "edge_insufficient")
            self.assertEqual(by_type["touch_below"].recommended_action, "maintain_filters_until_edge_improves")

    def test_no_positive_edge_is_not_called_sample_starved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            rows = [
                ["100", f"m{i}", "touch_above", "Q", "0.2", "0.07", "HOLD", "0", "-0.01", "-0.02", "净优势不足，等待更清晰的定价偏差", "SKIP", "", "", "-0.02", "skip"]
                for i in range(200)
            ]
            self._write_run(output_dir / "paper_run_100.csv", rows)

            review = build_strategy_review(str(output_dir), recent_runs=10)

            by_type = {row.market_type: row for row in review}
            self.assertEqual(by_type["touch_above"].status, "no_edge_available")
            self.assertEqual(by_type["touch_above"].recommended_action, "do_not_relax_filters_wait_for_market_edge")

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
