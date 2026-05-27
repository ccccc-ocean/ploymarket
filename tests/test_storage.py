import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.clob import PricePoint
from ploymarket_sim.paper import PaperSignalRow
from ploymarket_sim.polymarket import Market
from ploymarket_sim.storage import PaperPositionState, Storage


class StorageTests(unittest.TestCase):
    def test_saves_markets_and_price_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(True, str(Path(directory) / "test.sqlite"))
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
                ["yes-token", "no-token"],
                True,
                0.07,
                "crypto_fees",
                "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917",
            )

            storage.save_markets([market])
            storage.save_price_history("yes-token", [PricePoint(1, 0.5), PricePoint(2, 0.6)])
            stats = storage.stats()

            self.assertEqual(stats.market_count, 1)
            self.assertEqual(stats.price_point_count, 2)
            markets = storage.load_markets()
            self.assertEqual(len(markets), 1)
            self.assertEqual(markets[0].yes_token_id, "yes-token")
            self.assertEqual(markets[0].no_token_id, "no-token")
            self.assertEqual(markets[0].no_price, 0.5)
            self.assertEqual(markets[0].condition_id, "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917")
            history = storage.load_price_history("yes-token")
            self.assertEqual([point.price for point in history], [0.5, 0.6])
            fresh_markets = storage.load_markets_observed_after(0)
            self.assertEqual(len(fresh_markets), 1)
            fresh_history = storage.load_price_history_observed_after("yes-token", 0)
            self.assertEqual([point.price for point in fresh_history], [0.5, 0.6])
            quality = storage.market_history_stats()
            self.assertEqual(len(quality), 1)
            self.assertEqual(quality[0].price_point_count, 2)
            self.assertEqual(quality[0].first_timestamp, 1)
            self.assertEqual(quality[0].last_timestamp, 2)
            storage.save_paper_snapshots(
                [
                    PaperSignalRow(
                        123,
                        "m1",
                        "price_target",
                        "Q",
                        0.5,
                        0.02,
                        "HOLD",
                        0.0,
                        0.01,
                        -0.01,
                        "wait",
                        "SKIP",
                        "",
                        None,
                        -0.01,
                        "skip",
                    )
                ]
            )
            self.assertEqual(storage.snapshot_stats().snapshot_count, 1)
            storage.mark_stale_token("yes-token", "m1", "HTTP 404")
            self.assertTrue(storage.is_stale_token("yes-token"))
            self.assertFalse(storage.is_stale_token("missing-token"))
            storage.save_open_paper_position(
                PaperPositionState(
                    market_id="m1",
                    side="NO",
                    entry_price=0.7,
                    shares=10,
                    notional=7,
                    opened_at=123,
                    status="open",
                    closed_at=None,
                    realized_pnl=0.0,
                    cooldown_until=0,
                    peak_price=0.7,
                    partial_take_profit_count=0,
                )
            )
            position = storage.load_paper_position("m1")
            self.assertIsNotNone(position)
            self.assertEqual(storage.load_open_paper_market_ids(), {"m1"})
            assert position is not None
            self.assertEqual(position.side, "NO")
            self.assertEqual(position.peak_price, 0.7)
            storage.update_open_paper_position(
                PaperPositionState(
                    market_id="m1",
                    side="NO",
                    entry_price=0.7,
                    shares=5,
                    notional=3.5,
                    opened_at=123,
                    status="open",
                    closed_at=None,
                    realized_pnl=0.25,
                    cooldown_until=0,
                    peak_price=0.8,
                    partial_take_profit_count=1,
                )
            )
            updated = storage.load_paper_position("m1")
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated.shares, 5)
            self.assertEqual(updated.partial_take_profit_count, 1)
            storage.close_paper_position("m1", 456, 1.5, 4056)
            closed = storage.load_paper_position("m1")
            self.assertIsNotNone(closed)
            assert closed is not None
            self.assertEqual(closed.status, "closed")
            self.assertEqual(closed.cooldown_until, 4056)
            self.assertEqual(storage.load_open_paper_market_ids(), set())
            history = storage.load_closed_paper_position_history()
            self.assertEqual(len(history), 1)
            self.assertAlmostEqual(history[0].realized_pnl, 1.5)
            storage.save_open_paper_position(
                PaperPositionState(
                    market_id="m1",
                    side="NO",
                    entry_price=0.6,
                    shares=10,
                    notional=6,
                    opened_at=789,
                    status="open",
                    closed_at=None,
                    realized_pnl=0.0,
                    cooldown_until=0,
                    peak_price=0.6,
                    partial_take_profit_count=0,
                )
            )
            storage.close_paper_position("m1", 900, -1.0, 4500)
            history = storage.load_closed_paper_position_history()
            self.assertEqual(len(history), 2)
            self.assertAlmostEqual(sum(position.realized_pnl for position in history), 0.5)

    def test_disabled_storage_reports_zero_counts(self) -> None:
        storage = Storage(False, "unused.sqlite")

        stats = storage.stats()

        self.assertFalse(stats.enabled)
        self.assertEqual(stats.market_count, 0)
