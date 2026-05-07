import unittest

from ploymarket_sim.clob import PricePoint
from ploymarket_sim.config import SignalConfig
from ploymarket_sim.polymarket import Market
from ploymarket_sim.signals import build_signal


class SignalTests(unittest.TestCase):
    def test_positive_momentum_generates_buy_yes(self) -> None:
        market = Market(
            "1",
            "Will BTC be above X?",
            "btc-x",
            None,
            5000,
            1000,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
        )
        history = [PricePoint(i, 0.45) for i in range(24)] + [PricePoint(24 + i, 0.52) for i in range(6)]
        config = SignalConfig("1w", 60, 6, 24, 0.01, 0.015, 0.0, 0.92, 0.08)
        signal = build_signal(market, history, config)
        self.assertEqual(signal.action, "BUY_YES")
