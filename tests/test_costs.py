import unittest

from ploymarket_sim.costs import estimate_entry_cost, fee_amount, taker_fee_rate


class CostTests(unittest.TestCase):
    def test_taker_fee_is_highest_near_even_odds(self) -> None:
        self.assertGreater(taker_fee_rate(0.5, 0.02), taker_fee_rate(0.9, 0.02))

    def test_entry_cost_includes_fee_slippage_and_margin(self) -> None:
        estimate = estimate_entry_cost(0.5, 0.02, 25, 0.01)
        self.assertAlmostEqual(estimate.total_rate, 0.0175)

    def test_fee_amount_uses_polymarket_curve(self) -> None:
        self.assertAlmostEqual(fee_amount(100.0, 0.5, 0.02), 0.5)
