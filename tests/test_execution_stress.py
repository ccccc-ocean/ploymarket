import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.config import ExecutionStressConfig
from ploymarket_sim.execution_stress import build_execution_stress_rows, summarize_execution_stress, write_execution_stress_csv
from ploymarket_sim.paper import PaperSignalRow


def candidate(expected_net_edge: float = 0.02) -> PaperSignalRow:
    return PaperSignalRow(
        run_timestamp=123,
        market_id="m1",
        market_type="price_range_daily",
        question="Will BTC be above 78000?",
        yes_price=0.4,
        taker_fee_rate=0.02,
        action="BUY_NO",
        confidence=1.0,
        gross_edge=0.05,
        net_edge=expected_net_edge,
        reason="edge",
        execution_mode="TAKER",
        execution_side="BUY_NO",
        limit_price=0.6,
        expected_net_edge=expected_net_edge,
        execution_reason="live ask",
    )


class ExecutionStressTests(unittest.TestCase):
    def test_shadow_scenarios_cover_market_and_operational_risks(self) -> None:
        rows = build_execution_stress_rows([candidate()], ExecutionStressConfig(), 25.0)
        summary = summarize_execution_stress(rows)

        self.assertEqual(summary.candidates, 1)
        self.assertEqual(summary.scenarios, 8)
        self.assertEqual(summary.robust_candidates, 0)
        self.assertEqual(summary.market_stress_blocks, 1)
        self.assertEqual(summary.fail_safe_scenarios, 3)
        self.assertTrue(any(row.scenario == "cancel_failure_after_partial_fill" for row in rows))

    def test_latency_slippage_blocks_edge_that_does_not_survive(self) -> None:
        rows = build_execution_stress_rows([candidate(0.005)], ExecutionStressConfig(), 25.0)
        latency_rows = [row for row in rows if row.scenario.startswith("latency_adverse")]

        self.assertTrue(any(row.outcome == "BLOCK" for row in latency_rows))

    def test_csv_is_written_for_a_paper_run(self) -> None:
        rows = build_execution_stress_rows([candidate()], ExecutionStressConfig(), 25.0)
        with tempfile.TemporaryDirectory() as directory:
            path = write_execution_stress_csv(rows, directory, 123)

            self.assertEqual(path, Path(directory) / "execution_stress_123.csv")
            self.assertIn("signature_or_auth_failure", path.read_text(encoding="utf-8"))
