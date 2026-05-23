import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.cli import _paper_position_state_signal
from ploymarket_sim.cli import _paper_reentry_edge_too_weak
from ploymarket_sim.config import (
    ApiConfig,
    AppConfig,
    BacktestConfig,
    BtcFilterConfig,
    BtcPriceConfig,
    CacheConfig,
    ExecutionConfig,
    RiskConfig,
    SignalConfig,
    StorageConfig,
    UniverseConfig,
)
from ploymarket_sim.polymarket import Market
from ploymarket_sim.storage import PaperPositionState, Storage


def app_config(sqlite_path: str) -> AppConfig:
    return AppConfig(
        api=ApiConfig("", "", 1),
        cache=CacheConfig(False, "", 0, False),
        storage=StorageConfig(True, sqlite_path),
        btc_price=BtcPriceConfig("", "", "", ""),
        btc_filter=BtcFilterConfig(False, 1, -0.1, 0.5),
        universe=UniverseConfig(["btc"], 1, 1, "", True, False, 0.0, False),
        signal=SignalConfig("1w", 5, 3, 6, 0.0, 0.0, 0.0, 1.0, 0.0),
        execution=ExecutionConfig(False, 0.0, 0.0, 0.0, 0),
        risk=RiskConfig(
            starting_cash=1000.0,
            max_position_usdc=50.0,
            max_market_exposure_usdc=75.0,
            max_total_exposure_usdc=250.0,
            max_open_positions=5,
            daily_loss_limit_usdc=35.0,
            max_drawdown_pct=0.12,
            stop_loss_pct=0.25,
            take_profit_pct=0.25,
            max_spread=0.08,
            min_price=0.03,
            max_price=0.97,
            partial_take_profit_pct=0.125,
            partial_take_profit_fraction=0.5,
            trailing_stop_activation_pct=0.12,
            trailing_stop_drawdown_pct=0.06,
        ),
        backtest=BacktestConfig(25.0, 0.0, 0, "data"),
    )


def market() -> Market:
    return Market(
        "m1",
        "Will BTC be above 76000 on May 23?",
        "btc-above-76000-may-23",
        None,
        1000,
        100,
        True,
        ["Yes", "No"],
        [0.3, 0.7],
        ["yes", "no"],
        False,
        None,
        None,
    )


class PaperPositionTests(unittest.TestCase):
    def test_partial_take_profit_keeps_remainder_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            storage = Storage(True, config.storage.sqlite_path)
            storage.save_open_paper_position(
                PaperPositionState(
                    market_id="m1",
                    side="NO",
                    entry_price=0.7,
                    shares=100.0,
                    notional=70.0,
                    opened_at=100,
                    status="open",
                    closed_at=None,
                    realized_pnl=0.0,
                    cooldown_until=0,
                    peak_price=0.7,
                    partial_take_profit_count=0,
                )
            )

            signal = _paper_position_state_signal(config, storage, market(), yes_price=0.2, run_timestamp=200)

            self.assertIsNotNone(signal)
            assert signal is not None
            self.assertIn("分批止盈", signal.reason)
            position = storage.load_paper_position("m1")
            self.assertIsNotNone(position)
            assert position is not None
            self.assertEqual(position.status, "open")
            self.assertAlmostEqual(position.shares, 50.0)
            self.assertAlmostEqual(position.notional, 35.0)
            self.assertAlmostEqual(position.realized_pnl, 5.0)
            self.assertEqual(position.partial_take_profit_count, 1)

    def test_trailing_stop_closes_remaining_position_with_short_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            storage = Storage(True, config.storage.sqlite_path)
            storage.save_open_paper_position(
                PaperPositionState(
                    market_id="m1",
                    side="NO",
                    entry_price=0.7,
                    shares=50.0,
                    notional=35.0,
                    opened_at=100,
                    status="open",
                    closed_at=None,
                    realized_pnl=5.0,
                    cooldown_until=0,
                    peak_price=0.82,
                    partial_take_profit_count=1,
                )
            )

            signal = _paper_position_state_signal(config, storage, market(), yes_price=0.25, run_timestamp=200)

            self.assertIsNotNone(signal)
            assert signal is not None
            self.assertIn("移动止盈", signal.reason)
            position = storage.load_paper_position("m1")
            self.assertIsNotNone(position)
            assert position is not None
            self.assertEqual(position.status, "closed")
            self.assertEqual(position.cooldown_until, 800)
            self.assertGreater(position.realized_pnl, 0.0)

    def test_profitable_reentry_requires_stronger_edge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            storage = Storage(True, config.storage.sqlite_path)
            storage.save_open_paper_position(
                PaperPositionState(
                    market_id="m1",
                    side="NO",
                    entry_price=0.7,
                    shares=50.0,
                    notional=35.0,
                    opened_at=100,
                    status="closed",
                    closed_at=200,
                    realized_pnl=4.0,
                    cooldown_until=0,
                    peak_price=0.82,
                    partial_take_profit_count=1,
                )
            )

            self.assertTrue(_paper_reentry_edge_too_weak(config, storage, market(), 0.002, 0.0015))
            self.assertFalse(_paper_reentry_edge_too_weak(config, storage, market(), 0.003, 0.0015))


if __name__ == "__main__":
    unittest.main()
