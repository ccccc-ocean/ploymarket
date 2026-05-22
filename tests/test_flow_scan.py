import unittest

from ploymarket_sim.flow_scan import TradeFlow, summarize_market_flow
from ploymarket_sim.polymarket import Market


class FlowScanTests(unittest.TestCase):
    def test_summarizes_yes_and_no_pressure(self) -> None:
        market = Market(
            "m1",
            "Will Bitcoin be above $78,000?",
            "btc-above-78k",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.4, 0.6],
            ["yes", "no"],
            False,
            None,
            None,
            "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917",
        )
        trades = [
            TradeFlow("0x1", "BUY", "YES", 1000, 0.40, 1),
            TradeFlow("0x2", "SELL", "NO", 250, 0.60, 2),
            TradeFlow("0x3", "BUY", "NO", 100, 0.60, 3),
        ]

        row = summarize_market_flow(market, trades, latest_btc_price=76000, large_trade_usdc=300)

        self.assertEqual(row.trade_count, 3)
        self.assertEqual(row.large_trade_count, 1)
        self.assertEqual(row.flow_signal, "YES_PRESSURE")
        self.assertEqual(row.strike_risk, "far_above_spot")


if __name__ == "__main__":
    unittest.main()
