import unittest

from ploymarket_sim.backtest import BacktestResult, Trade
from ploymarket_sim.polymarket import Market
from ploymarket_sim.summary import aggregate_summaries, summarize_all, summarize_market


def market(question: str = "Will Bitcoin reach $100,000 in May?") -> Market:
    return Market("m1", question, "btc", None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)


class SummaryTests(unittest.TestCase):
    def test_summarizes_market_backtest_result(self) -> None:
        result = BacktestResult(
            "m1",
            "Will Bitcoin reach $100,000 in May?",
            [
                Trade(1, "m1", "BUY_YES", 0.5, 25.0, 0.1, 0.05, 0.0, 0.04, "entry"),
                Trade(2, "m1", "SELL_YES", 0.6, 30.0, 0.1, 0.0, 4.75, 0.0, "exit"),
            ],
            1004.75,
            4.75,
        )

        summary = summarize_market(market(), result)

        self.assertEqual(summary.market_type, "price_target")
        self.assertEqual(summary.taker_fee_rate, 0.0)
        self.assertEqual(summary.entry_count, 1)
        self.assertEqual(summary.exit_count, 1)
        self.assertEqual(summary.win_count, 1)
        self.assertAlmostEqual(summary.win_rate, 1.0)
        self.assertAlmostEqual(summary.total_fees, 0.2)

    def test_aggregates_summaries(self) -> None:
        result = BacktestResult("m1", "Will Bitcoin reach $100,000 in May?", [], 1000.0, 0.0)
        summary = summarize_market(market(), result)

        all_summary = summarize_all([summary])
        by_type = aggregate_summaries([summary])

        self.assertEqual(all_summary.market_type, "all")
        self.assertEqual(all_summary.market_count, 1)
        self.assertEqual(by_type[0].market_type, "price_target")
