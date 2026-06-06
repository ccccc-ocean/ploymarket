import csv
import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.live_universe_report import build_live_universe_report, write_live_universe_report_csv
from ploymarket_sim.paper_sample_report import PaperSampleRow
from ploymarket_sim.polymarket import Market


def market(question: str, market_id: str = "1") -> Market:
    return Market(
        market_id,
        question,
        "btc",
        None,
        1000,
        1000,
        True,
        ["Yes", "No"],
        [0.5, 0.5],
        ["yes", "no"],
        False,
        None,
        None,
    )


def sample_row(market_type: str, takers: int, positive_edge_skips: int, sample_status: str) -> PaperSampleRow:
    return PaperSampleRow(
        market_type=market_type,
        recent_runs=288,
        unique_market_count=1,
        row_count=max(1, takers + positive_edge_skips),
        taker_count=takers,
        buy_yes_taker_count=takers,
        buy_no_taker_count=0,
        probe_taker_count=takers,
        skip_count=positive_edge_skips,
        positive_edge_skip_count=positive_edge_skips,
        taker_rate=0.0,
        probe_taker_rate=1.0 if takers else 0.0,
        max_expected_edge=0.1,
        average_taker_edge=0.05,
        top_probe_families="test_family:1" if takers else "",
        sample_status=sample_status,
    )


class LiveUniverseReportTests(unittest.TestCase):
    def test_distinguishes_no_live_markets_from_live_sample_starvation(self) -> None:
        markets = [
            market("Will the price of Bitcoin be above $70,000 on June 4?", "above"),
            market("Will Bitcoin dip to $68,000 in June?", "touch-below"),
        ]
        samples = [
            sample_row("above_below_expiry", takers=0, positive_edge_skips=4, sample_status="sample_starved"),
            sample_row("range_bucket", takers=0, positive_edge_skips=3, sample_status="sample_starved"),
        ]

        rows = build_live_universe_report(markets, samples)
        by_type = {row.market_type: row for row in rows}

        self.assertEqual(by_type["above_below_expiry"].live_count, 1)
        self.assertEqual(by_type["above_below_expiry"].universe_status, "sample_starved_with_live_markets")
        self.assertEqual(by_type["range_bucket"].live_count, 0)
        self.assertEqual(by_type["range_bucket"].universe_status, "no_live_markets")
        self.assertEqual(by_type["touch_below"].live_count, 1)
        self.assertEqual(by_type["touch_below"].universe_status, "live_available")

    def test_writes_live_universe_csv(self) -> None:
        rows = build_live_universe_report(
            [market("Will the price of Bitcoin be above $70,000 on June 4?")],
            [sample_row("above_below_expiry", takers=1, positive_edge_skips=2, sample_status="probe_only")],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = write_live_universe_report_csv(rows, tmp)
            self.assertTrue(path.exists())
            with Path(path).open("r", newline="", encoding="utf-8") as file:
                records = list(csv.DictReader(file))
            self.assertIn("market_type", records[0])
            self.assertIn("universe_status", records[0])


if __name__ == "__main__":
    unittest.main()
