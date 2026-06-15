import unittest

from ploymarket_sim.clob import PricePoint
from ploymarket_sim.config import SignalConfig
from ploymarket_sim.polymarket import Market
from ploymarket_sim.signals import Signal, apply_entry_policy, build_signal


class SignalTests(unittest.TestCase):
    def test_entry_policy_blocks_direction_outside_allowlist(self) -> None:
        market = Market(
            "1",
            "Will the price of Bitcoin be above $78,000 on May 22?",
            "btc-above-78k",
            None,
            5000,
            1000,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
            False,
            None,
            None,
        )
        config = SignalConfig(
            "1w",
            60,
            6,
            24,
            0.01,
            0.015,
            0.0,
            0.92,
            0.08,
            ["above_below_expiry:BUY_YES"],
            0.01,
        )

        signal = apply_entry_policy(market, Signal("BUY_NO", 1.0, 0.05, 0.04, "test"), config)

        self.assertEqual(signal.action, "HOLD")
        self.assertIn("白名单", signal.reason)

    def test_entry_policy_requires_minimum_net_edge(self) -> None:
        market = Market(
            "1",
            "Will the price of Bitcoin be above $78,000 on May 22?",
            "btc-above-78k",
            None,
            5000,
            1000,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
            False,
            None,
            None,
        )
        config = SignalConfig(
            "1w",
            60,
            6,
            24,
            0.01,
            0.015,
            0.0,
            0.92,
            0.08,
            ["above_below_expiry:BUY_YES"],
            0.01,
        )

        signal = apply_entry_policy(market, Signal("BUY_YES", 1.0, 0.05, 0.009, "test"), config)

        self.assertEqual(signal.action, "HOLD")
        self.assertIn("净 edge 不足", signal.reason)

    def test_positive_momentum_generates_buy_yes(self) -> None:
        market = Market(
            "1",
            "Bitcoin Up or Down on May 22?",
            "btc-up-down",
            None,
            5000,
            1000,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(i, 0.45) for i in range(24)] + [PricePoint(24 + i, 0.52) for i in range(6)]
        config = SignalConfig("1w", 60, 6, 24, 0.01, 0.015, 0.0, 0.92, 0.08)
        signal = build_signal(market, history, config)
        self.assertEqual(signal.action, "BUY_YES")

    def test_negative_daily_range_momentum_generates_buy_no(self) -> None:
        market = Market(
            "1",
            "Will the price of Bitcoin be above $78,000 on May 22?",
            "btc-above-78k",
            None,
            5000,
            1000,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(i, 0.55) for i in range(24)] + [PricePoint(24 + i, 0.45) for i in range(6)]
        config = SignalConfig("1w", 60, 6, 24, 0.01, 0.015, 0.0, 0.92, 0.08)

        signal = build_signal(market, history, config)

        self.assertEqual(signal.action, "BUY_NO")

    def test_buy_no_respects_no_price_floor(self) -> None:
        market = Market(
            "1",
            "Will the price of Bitcoin be above $78,000 on May 22?",
            "btc-above-78k",
            None,
            5000,
            1000,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(i, 0.99) for i in range(24)] + [PricePoint(24 + i, 0.95) for i in range(6)]
        config = SignalConfig("1w", 60, 6, 24, 0.01, 0.015, 0.0, 0.92, 0.08)

        signal = build_signal(market, history, config)

        self.assertEqual(signal.action, "HOLD")
        self.assertIn("NO 价格太接近 0", signal.reason)

    def test_above_below_expiry_allows_buy_yes_after_unblock(self) -> None:
        # Regression: signals.py previously gated BUY_YES to up_down_short_term
        # only, while strategy_profiles.py tuned thresholds for above_below_expiry.
        # The ×2/×3 BUY_YES multipliers were dead code. Critical #1 unblocks
        # this path; this test pins the new behaviour.
        market = Market(
            "1",
            "Will the price of Bitcoin be above $78,000 on May 22?",
            "btc-above-78k",
            None,
            5000,
            1000,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(i, 0.40) for i in range(24)] + [PricePoint(24 + i, 0.55) for i in range(6)]
        config = SignalConfig("1w", 60, 6, 24, 0.01, 0.015, 0.0, 0.92, 0.08)

        signal = build_signal(market, history, config)

        self.assertEqual(signal.action, "BUY_YES")

    def test_above_below_expiry_buy_yes_respects_multiplied_threshold(self) -> None:
        # The ×2 momentum / ×3 edge multipliers for above_below_expiry must
        # actually gate weak signals; otherwise unblocking allow_buy_yes would
        # have flooded entries.
        market = Market(
            "1",
            "Will the price of Bitcoin be above $78,000 on May 22?",
            "btc-above-78k",
            None,
            5000,
            1000,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
            False,
            None,
            None,
        )
        # Momentum ≈ +0.015 — would have passed the base threshold (0.01) but
        # must fail the ×2 above_below_expiry threshold (0.02).
        history = [PricePoint(i, 0.50) for i in range(24)] + [PricePoint(24 + i, 0.52) for i in range(6)]
        config = SignalConfig("1w", 60, 6, 24, 0.01, 0.015, 0.0, 0.92, 0.08)

        signal = build_signal(market, history, config)

        self.assertEqual(signal.action, "HOLD")

    def test_negative_price_target_momentum_generates_buy_no(self) -> None:
        market = Market(
            "1",
            "Will Bitcoin reach $80,000 May 18-24?",
            "btc-reach-80k",
            None,
            5000,
            1000,
            True,
            ["Yes", "No"],
            [0.5, 0.5],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(i, 0.55) for i in range(24)] + [PricePoint(24 + i, 0.45) for i in range(6)]
        config = SignalConfig("1w", 60, 6, 24, 0.01, 0.015, 0.0, 0.92, 0.08)

        signal = build_signal(market, history, config)

        self.assertEqual(signal.action, "BUY_NO")
