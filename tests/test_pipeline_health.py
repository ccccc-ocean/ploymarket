import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.pipeline_health import (
    append_event,
    assess_health,
    load_state,
    mark_finished,
    mark_started,
)


class PipelineHealthTests(unittest.TestCase):
    def test_failed_run_is_unhealthy_even_after_previous_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mark_started(directory, "live_paper", "one", 100)
            mark_finished(directory, "live_paper", "one", 110, 0, "flow-scan")
            mark_started(directory, "live_paper", "two", 200)
            state = mark_finished(directory, "live_paper", "two", 210, 1, "paper-run")

            assessment = assess_health(state, 211, 600, 240)

            self.assertFalse(assessment.healthy)
            self.assertEqual(assessment.reason, "failed_at_paper-run")
            self.assertEqual(state["last_success_at"], 110)

    def test_stale_success_and_stale_running_need_recovery(self) -> None:
        success = {"status": "success", "last_success_at": 100}
        running = {"status": "running", "started_at": 100}

        self.assertFalse(assess_health(success, 701, 600, 240).healthy)
        self.assertFalse(assess_health(running, 341, 600, 240).healthy)
        self.assertTrue(assess_health(running, 340, 600, 240).healthy)

    def test_state_is_persisted_and_watchdog_events_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mark_started(directory, "research", "run-a", 100, "stale_lock_removed")
            stored = load_state(directory, "research")
            path = append_event(directory, 120, "research", "failed_at_backtest", "retry", "success")

            self.assertEqual(stored["recovery_reason"], "stale_lock_removed")
            self.assertTrue(Path(path).exists())
            self.assertIn("failed_at_backtest,retry,success", Path(path).read_text())


if __name__ == "__main__":
    unittest.main()
