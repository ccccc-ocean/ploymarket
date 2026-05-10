import unittest

from ploymarket_sim.paper import build_paper_signal_row, summarize_paper_rows
from ploymarket_sim.polymarket import Market
from ploymarket_sim.signals import Signal
from ploymarket_sim.execution import ExecutionPlan


class PaperTests(unittest.TestCase):
    def test_builds_paper_signal_row(self) -> None:
        market = Market(
            "m1",
            "Will Bitcoin reach $100,000 in May?",
            "btc-100k",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
            True,
            0.07,
            "crypto_fees",
        )
        signal = Signal("BUY_YES", 0.5, 0.08, 0.04, "edge")

        row = build_paper_signal_row(market, signal, 0.02, 123)

        self.assertEqual(row.market_type, "price_target")
        self.assertEqual(row.taker_fee_rate, 0.07)
        self.assertEqual(row.action, "BUY_YES")
        self.assertEqual(row.execution_mode, "SKIP")

    def test_summarizes_paper_rows(self) -> None:
        market = Market("m1", "Will BTC be above X?", "btc", None, 1000, 100, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)
        rows = [
            build_paper_signal_row(
                market,
                Signal("BUY_YES", 0.5, 0.08, 0.04, "edge"),
                0.02,
                123,
                ExecutionPlan("TAKER", "BUY_YES", 0.5, 0.02, 0.04, "take"),
            ),
            build_paper_signal_row(market, Signal("HOLD", 0.0, 0.0, 0.0, "wait"), 0.02, 123),
        ]

        summary = summarize_paper_rows(rows)

        self.assertEqual(summary["markets"], 2)
        self.assertEqual(summary["buy_yes"], 1)
        self.assertEqual(summary["hold"], 1)
        self.assertEqual(summary["taker"], 1)
        self.assertEqual(summary["skip"], 1)
