import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.probe_performance_report import ProbePerformanceRow
from ploymarket_sim.strategy_autotune_report import (
    AutotuneContext,
    build_strategy_autotune_report,
    write_strategy_autotune_report_csv,
)
from ploymarket_sim.strategy_review import StrategyReviewRow


class StrategyAutotuneReportTests(unittest.TestCase):
    def test_prioritizes_disabled_probe_families_and_sample_starvation(self) -> None:
        strategy_rows = [
            StrategyReviewRow(
                "above_below_expiry",
                "positive_edge_blocked",
                "allow_small_size_certainty_no_or_yes_probe",
                "blocked",
                0,
                0,
                25,
                0.12,
                "price_too_high_or_payout_too_low:25/25",
            )
        ]
        probe_rows = [
            ProbePerformanceRow("range_bucket_yes", "range_bucket", 2, 2, 0, -1.5, 0, 2, 0.0, -0.75, 100),
        ]
        context = AutotuneContext(5, 3, 15.0, 30.0, ["range_bucket_yes"], 8)

        rows = build_strategy_autotune_report(strategy_rows, probe_rows, context)

        self.assertEqual(rows[0].action, "redesign_range_bucket_with_boundary_and_time_filter")
        self.assertTrue(any(row.action == "allow_small_size_certainty_no_or_yes_probe" for row in rows))
        self.assertTrue(any(row.action == "search_probe_candidates_before_next_relaxation" for row in rows))

    def test_disabled_regime_challenge_recommends_specific_redesign(self) -> None:
        rows = build_strategy_autotune_report(
            [],
            [],
            AutotuneContext(2, 3, 6.0, 30.0, ["regime_filter_challenge"], 8),
        )

        by_scope = {row.scope: row for row in rows}
        row = by_scope["probe_family/regime_filter_challenge"]
        self.assertEqual(row.action, "redesign_require_strike_retreat_before_regime_challenge")
        self.assertIn("明确远离 strike", row.reason)

    def test_disabled_touch_below_no_recommends_specific_redesign(self) -> None:
        rows = build_strategy_autotune_report(
            [],
            [],
            AutotuneContext(2, 3, 6.0, 30.0, ["touch_below_no"], 8),
        )

        by_scope = {row.scope: row for row in rows}
        row = by_scope["probe_family/touch_below_no"]
        self.assertEqual(row.action, "redesign_touch_below_no_with_larger_target_buffer")
        self.assertIn("更大的 target 距离", row.reason)

    def test_disabled_touch_below_yes_variants_stay_disabled_until_path_model(self) -> None:
        rows = build_strategy_autotune_report(
            [],
            [],
            AutotuneContext(
                2,
                3,
                6.0,
                30.0,
                ["touch_below_discount_yes", "touch_below_momentum_yes"],
                8,
            ),
        )

        by_scope = {row.scope: row for row in rows}
        self.assertEqual(
            by_scope["probe_family/touch_below_discount_yes"].action,
            "keep_touch_below_discount_yes_disabled_until_path_edge_model",
        )
        self.assertEqual(
            by_scope["probe_family/touch_below_momentum_yes"].action,
            "keep_touch_below_momentum_yes_disabled_until_path_edge_model",
        )

    def test_marks_profitable_probe_family_for_cautious_promotion(self) -> None:
        rows = build_strategy_autotune_report(
            [],
            [
                ProbePerformanceRow(
                    "regime_filter_challenge",
                    "above_below_expiry",
                    12,
                    12,
                    0,
                    2.4,
                    8,
                    4,
                    8 / 12,
                    0.2,
                    200,
                )
            ],
            AutotuneContext(2, 4, 6.0, 30.0, [], 0),
        )

        self.assertTrue(any(row.action == "keep_probe_active_consider_cautious_promotion" for row in rows))

    def test_recent_taker_wait_is_not_mislabeled_as_probe_slots_full(self) -> None:
        rows = build_strategy_autotune_report(
            [],
            [],
            AutotuneContext(
                open_positions=9,
                probe_slots=0,
                open_exposure_usdc=23.3,
                probe_max_exposure_usdc=30.0,
                disabled_probe_families=[],
                zero_taker_streak=0,
                probe_zero_run_threshold=1,
            ),
        )

        by_scope = {row.scope: row for row in rows}
        self.assertEqual(by_scope["probe_slots"].status, "recent_taker_wait")
        self.assertEqual(by_scope["probe_slots"].action, "wait_for_next_zero_taker_run")

    def test_waits_for_open_probe_resolution_before_expanding_market_type(self) -> None:
        rows = build_strategy_autotune_report(
            [
                StrategyReviewRow(
                    "touch_below",
                    "probe_active",
                    "monitor_probe_pnl",
                    "active",
                    2,
                    2,
                    59,
                    0.28,
                    "type_side_not_enabled:43/43",
                )
            ],
            [
                ProbePerformanceRow("touch_below_no", "touch_below", 1, 0, 1, 0.0, 0, 0, 0.0, 0.0, 100),
                ProbePerformanceRow("touch_below_certainty_no", "touch_below", 1, 0, 1, 0.0, 0, 0, 0.0, 0.0, 120),
            ],
            AutotuneContext(3, 2, 9.0, 30.0, [], 2),
        )

        by_scope = {row.scope: row for row in rows}
        self.assertEqual(by_scope["market_type/touch_below/pending_probe"].status, "type_probe_pending")
        self.assertEqual(
            by_scope["market_type/touch_below/pending_probe"].action,
            "wait_for_open_probe_resolution_before_expanding_type",
        )

    def test_no_edge_available_recommends_waiting_for_positive_edge(self) -> None:
        rows = build_strategy_autotune_report(
            [
                StrategyReviewRow(
                    "range_bucket",
                    "no_edge_available",
                    "do_not_relax_filters_wait_for_market_edge",
                    "no edge",
                    0,
                    0,
                    0,
                    -0.01,
                    "edge_too_low:0/200",
                )
            ],
            [],
            AutotuneContext(0, 5, 0.0, 30.0, [], 10),
        )

        by_scope = {row.scope: row for row in rows}
        self.assertEqual(by_scope["market_type/range_bucket"].status, "no_edge_available")
        self.assertEqual(by_scope["market_type/range_bucket"].action, "do_not_relax_filters_wait_for_positive_edge")

    def test_writes_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = build_strategy_autotune_report([], [], AutotuneContext(0, 5, 0.0, 30.0, [], 0))
            path = write_strategy_autotune_report_csv(rows, tmp)

            self.assertTrue(path.exists())
            self.assertIn("strategy_autotune_report.csv", str(path))


if __name__ == "__main__":
    unittest.main()
