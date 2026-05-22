import unittest

from ploymarket_sim.clob import TokenQuote
from ploymarket_sim.config import load_config
from ploymarket_sim.polymarket import Market
from ploymarket_sim.spread_scan import build_spread_scan_row, scan_spreads


class SpreadScanTests(unittest.TestCase):
    def test_recommends_buy_both_when_complete_set_is_cheap(self) -> None:
        row = build_spread_scan_row(
            load_config("config/default.toml"),
            _market(),
            TokenQuote("yes-token", bid=0.47, ask=0.48),
            TokenQuote("no-token", bid=0.48, ask=0.49),
        )

        self.assertEqual(row.recommendation, "BUY_BOTH")
        self.assertIsNotNone(row.buy_pair_edge)
        assert row.buy_pair_edge is not None
        self.assertGreater(row.buy_pair_edge, 0)

    def test_recommends_sell_both_when_complete_set_bid_is_rich(self) -> None:
        row = build_spread_scan_row(
            load_config("config/default.toml"),
            _market(),
            TokenQuote("yes-token", bid=0.52, ask=0.54),
            TokenQuote("no-token", bid=0.52, ask=0.54),
        )

        self.assertEqual(row.recommendation, "SELL_BOTH")
        self.assertIsNotNone(row.sell_pair_edge)
        assert row.sell_pair_edge is not None
        self.assertGreater(row.sell_pair_edge, 0)

    def test_skips_when_no_net_spread_edge(self) -> None:
        row = build_spread_scan_row(
            load_config("config/default.toml"),
            _market(),
            TokenQuote("yes-token", bid=0.49, ask=0.51),
            TokenQuote("no-token", bid=0.48, ask=0.52),
        )

        self.assertEqual(row.recommendation, "SKIP")

    def test_skips_recent_stale_tokens_without_requesting_books(self) -> None:
        class FakeStorage:
            def is_stale_token(self, token_id: str) -> bool:
                return token_id == "yes-token"

        rows = scan_spreads(load_config("config/default.toml"), [_market()], FakeStorage())

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].recommendation, "SKIP")
        self.assertIn("stale token", rows[0].reason)


def _market() -> Market:
    return Market(
        "m1",
        "Will Bitcoin be above $100,000?",
        "btc-above-100k",
        None,
        1000,
        100,
        True,
        ["Yes", "No"],
        [0.5, 0.5],
        ["yes-token", "no-token"],
        False,
        None,
        None,
    )
