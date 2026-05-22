import unittest

from ploymarket_sim.config import BacktestConfig, ExecutionConfig, SignalConfig
from ploymarket_sim.execution import plan_execution
from ploymarket_sim.polymarket import Market
from ploymarket_sim.signals import Signal


def market(price: float = 0.5) -> Market:
    return Market("m1", "Will BTC be above X?", "btc", None, 1000, 100, True, ["Yes", "No"], [price, 1 - price], ["yes", "no"], False, None, None)


class ExecutionTests(unittest.TestCase):
    def test_taker_when_signal_is_buy_yes(self) -> None:
        plan = plan_execution(
            market(),
            Signal("BUY_YES", 0.5, 0.08, 0.04, "edge"),
            SignalConfig("1w", 60, 6, 24, 0.015, 0.025, 0.01, 0.92, 0.08),
            BacktestConfig(25.0, 0.02, 25, "data"),
            ExecutionConfig(True, 0.01, 0.015, 0.0, 300),
        )

        self.assertEqual(plan.mode, "TAKER")
        self.assertEqual(plan.side, "BUY_YES")

    def test_taker_when_signal_is_buy_no(self) -> None:
        plan = plan_execution(
            market(0.4),
            Signal("BUY_NO", 0.5, 0.08, 0.04, "edge"),
            SignalConfig("1w", 60, 6, 24, 0.015, 0.025, 0.01, 0.92, 0.08),
            BacktestConfig(25.0, 0.02, 25, "data"),
            ExecutionConfig(True, 0.01, 0.015, 0.0, 300),
        )

        self.assertEqual(plan.mode, "TAKER")
        self.assertEqual(plan.side, "BUY_NO")
        self.assertAlmostEqual(plan.limit_price or 0.0, 0.6)

    def test_maker_when_gross_edge_survives_maker_costs(self) -> None:
        plan = plan_execution(
            market(),
            Signal("HOLD", 0.0, 0.025, 0.005, "wait"),
            SignalConfig("1w", 60, 6, 24, 0.015, 0.025, 0.01, 0.92, 0.08),
            BacktestConfig(25.0, 0.02, 25, "data"),
            ExecutionConfig(True, 0.01, 0.015, 0.0, 300),
        )

        self.assertEqual(plan.mode, "MAKER")
        self.assertAlmostEqual(plan.limit_price or 0.0, 0.49)
        self.assertGreaterEqual(plan.expected_net_edge, 0.015)

    def test_skip_when_edge_is_too_small(self) -> None:
        plan = plan_execution(
            market(),
            Signal("HOLD", 0.0, 0.01, -0.01, "wait"),
            SignalConfig("1w", 60, 6, 24, 0.015, 0.025, 0.01, 0.92, 0.08),
            BacktestConfig(25.0, 0.02, 25, "data"),
            ExecutionConfig(True, 0.01, 0.015, 0.0, 300),
        )

        self.assertEqual(plan.mode, "SKIP")
