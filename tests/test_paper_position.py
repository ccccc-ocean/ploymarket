import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ploymarket_sim.btc_price import BtcCandle
from ploymarket_sim.cli import _paper_position_state_signal
from ploymarket_sim.cli import _paper_position_signal_with_live_quote
from ploymarket_sim.cli import _paper_reentry_edge_too_weak
from ploymarket_sim.cli import _fresh_paper_btc_candles
from ploymarket_sim.cli import _live_paper_entry_plan
from ploymarket_sim.cli import _market_discovery_is_healthy
from ploymarket_sim.cli import _paper_run_data_degraded
from ploymarket_sim.cli import _paper_markets_including_open_positions
from ploymarket_sim.cli import _realtime_market_discovery_is_healthy
from ploymarket_sim.cli import _strategy_loss_pause_blocks_entry
from ploymarket_sim.clob import TokenQuote
from ploymarket_sim.http import HttpError
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
from ploymarket_sim.signals import Signal
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


def target_market() -> Market:
    return Market(
        "target-1",
        "Will Bitcoin reach $85,000 in May?",
        "bitcoin-reach-85000-in-may",
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


def resolved_market(yes_price: float, no_price: float) -> Market:
    return Market(
        "m1",
        "Will BTC be above 76000 on May 23?",
        "btc-above-76000-may-23",
        "2026-05-23T16:00:00Z",
        1000,
        100,
        True,
        ["Yes", "No"],
        [yes_price, no_price],
        ["yes", "no"],
        False,
        None,
        None,
        closed=True,
        resolution_status="resolved",
    )


class PaperPositionTests(unittest.TestCase):
    def test_realtime_live_discovery_is_not_rejected_by_accumulated_research_universe(self) -> None:
        live_markets = [market()] * 56
        local_markets = [market()] * 115

        self.assertFalse(_market_discovery_is_healthy(live_markets, local_markets))
        self.assertTrue(_realtime_market_discovery_is_healthy(live_markets))

    def test_empty_all_market_paper_run_is_a_live_pipeline_failure(self) -> None:
        self.assertTrue(_paper_run_data_degraded("all", []))
        self.assertFalse(_paper_run_data_degraded("price_target", []))
        self.assertFalse(_paper_run_data_degraded("all", [market()]))

    def test_open_position_market_is_monitored_when_not_in_live_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            storage = Storage(True, config.storage.sqlite_path)
            stored_market = target_market()
            storage.save_markets([stored_market])
            storage.save_open_paper_position(
                PaperPositionState(
                    market_id=stored_market.id,
                    side="YES",
                    entry_price=0.7,
                    shares=10.0,
                    notional=7.0,
                    opened_at=100,
                    status="open",
                    closed_at=None,
                    realized_pnl=0.0,
                    cooldown_until=0,
                    peak_price=0.7,
                    partial_take_profit_count=0,
                )
            )

            markets = _paper_markets_including_open_positions(storage, [market()], "all")

            self.assertEqual({item.id for item in markets}, {"m1", "target-1"})

    def test_stale_btc_candles_are_not_accepted_for_paper_entries(self) -> None:
        config = app_config("unused.sqlite")
        candles = [BtcCandle(100, 1.0, 1.0, 1.0, 1.0)]

        self.assertEqual(_fresh_paper_btc_candles(config, candles, 100 + 901), [])
        self.assertEqual(_fresh_paper_btc_candles(config, candles, 100 + 900), candles)

    def test_live_entry_uses_orderbook_ask(self) -> None:
        config = app_config("unused.sqlite")
        signal = Signal("BUY_NO", 1.0, 0.05, 0.04, "edge")
        with patch("ploymarket_sim.cli.get_token_quote", return_value=TokenQuote("no", bid=0.68, ask=0.70)):
            repriced_signal, plan = _live_paper_entry_plan(config, market(), signal, config, 0.32)

        self.assertEqual(repriced_signal.action, "BUY_NO")
        self.assertEqual(plan.mode, "TAKER")
        self.assertAlmostEqual(plan.limit_price or 0.0, 0.70)

    def test_live_entry_skips_when_orderbook_spread_is_too_wide(self) -> None:
        config = app_config("unused.sqlite")
        signal = Signal("BUY_NO", 1.0, 0.05, 0.04, "edge")
        with patch("ploymarket_sim.cli.get_token_quote", return_value=TokenQuote("no", bid=0.55, ask=0.70)):
            repriced_signal, plan = _live_paper_entry_plan(config, market(), signal, config, 0.32)

        self.assertEqual(repriced_signal.action, "HOLD")
        self.assertEqual(plan.mode, "SKIP")

    def test_resolved_position_is_settled_when_orderbook_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            storage = Storage(True, config.storage.sqlite_path)
            storage.save_open_paper_position(
                PaperPositionState(
                    market_id="m1",
                    side="NO",
                    entry_price=0.9,
                    shares=10.0,
                    notional=9.0,
                    opened_at=100,
                    status="open",
                    closed_at=None,
                    realized_pnl=0.0,
                    cooldown_until=0,
                    peak_price=0.9,
                    partial_take_profit_count=0,
                )
            )

            with patch("ploymarket_sim.cli.get_token_quote", side_effect=HttpError("HTTP Error 404: Not Found")):
                with patch("ploymarket_sim.cli.get_market_by_id", return_value=resolved_market(0.0, 1.0)):
                    signal = _paper_position_signal_with_live_quote(config, storage, market(), 0.0, 200)

            self.assertIsNotNone(signal)
            assert signal is not None
            self.assertIn("按已解析结果结算", signal.reason)
            position = storage.load_paper_position("m1")
            self.assertIsNotNone(position)
            assert position is not None
            self.assertEqual(position.status, "closed")
            self.assertAlmostEqual(position.realized_pnl, 1.0)

    def test_unresolved_position_stays_open_when_orderbook_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            storage = Storage(True, config.storage.sqlite_path)
            storage.save_open_paper_position(
                PaperPositionState("m1", "YES", 0.7, 10.0, 7.0, 100, "open", None, 0.0, 0, 0.7, 0)
            )

            unresolved = market()
            with patch("ploymarket_sim.cli.get_token_quote", side_effect=HttpError("HTTP Error 404: Not Found")):
                with patch("ploymarket_sim.cli.get_market_by_id", return_value=unresolved):
                    signal = _paper_position_signal_with_live_quote(config, storage, market(), 0.3, 200)

            self.assertIsNotNone(signal)
            assert signal is not None
            self.assertIn("实时 bid 获取失败", signal.reason)
            self.assertEqual(storage.load_paper_position("m1").status, "open")

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

    def test_target_stop_loss_uses_longer_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            storage = Storage(True, config.storage.sqlite_path)
            storage.save_open_paper_position(
                PaperPositionState(
                    market_id="target-1",
                    side="YES",
                    entry_price=0.7,
                    shares=50.0,
                    notional=35.0,
                    opened_at=100,
                    status="open",
                    closed_at=None,
                    realized_pnl=0.0,
                    cooldown_until=0,
                    peak_price=0.7,
                    partial_take_profit_count=0,
                )
            )

            signal = _paper_position_state_signal(config, storage, target_market(), yes_price=0.5, run_timestamp=200)

            self.assertIsNotNone(signal)
            assert signal is not None
            self.assertIn("触发止损", signal.reason)
            position = storage.load_paper_position("target-1")
            self.assertIsNotNone(position)
            assert position is not None
            self.assertEqual(position.status, "closed")
            self.assertEqual(position.cooldown_until, 200 + config.risk.target_stop_cooldown_seconds)

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

    def test_strategy_loss_pause_blocks_same_market_type_direction_and_side(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            storage = Storage(True, config.storage.sqlite_path)
            storage.save_markets([market(), Market("m2", market().question, "btc-above-2", None, 1000, 100, True, ["Yes", "No"], [0.3, 0.7], ["yes2", "no2"], False, None, None)])
            for market_id in ["m1", "m2"]:
                storage.save_open_paper_position(
                    PaperPositionState(
                        market_id=market_id,
                        side="NO",
                        entry_price=0.7,
                        shares=10.0,
                        notional=7.0,
                        opened_at=100,
                        status="open",
                        closed_at=None,
                        realized_pnl=0.0,
                        cooldown_until=0,
                        peak_price=0.7,
                        partial_take_profit_count=0,
                    )
                )
                storage.close_paper_position(market_id, 200, -1.0, 300)

            blocked, reason = _strategy_loss_pause_blocks_entry(config, storage, market(), "BUY_NO", 400)

            self.assertTrue(blocked)
            self.assertIn("同类方向连续止损", reason)

    def test_strategy_loss_pause_does_not_block_different_direction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            storage = Storage(True, config.storage.sqlite_path)
            below_market = Market("below-1", "Will Bitcoin dip to $72,000 in May?", "btc-dip-72000", None, 1000, 100, True, ["Yes", "No"], [0.3, 0.7], ["yes3", "no3"], False, None, None)
            storage.save_markets([market(), Market("m2", market().question, "btc-above-2", None, 1000, 100, True, ["Yes", "No"], [0.3, 0.7], ["yes2", "no2"], False, None, None), below_market])
            for market_id in ["m1", "m2"]:
                storage.save_open_paper_position(
                    PaperPositionState(
                        market_id=market_id,
                        side="NO",
                        entry_price=0.7,
                        shares=10.0,
                        notional=7.0,
                        opened_at=100,
                        status="open",
                        closed_at=None,
                        realized_pnl=0.0,
                        cooldown_until=0,
                        peak_price=0.7,
                        partial_take_profit_count=0,
                    )
                )
                storage.close_paper_position(market_id, 200, -1.0, 300)

            blocked, _reason = _strategy_loss_pause_blocks_entry(config, storage, below_market, "BUY_NO", 400)

            self.assertFalse(blocked)


if __name__ == "__main__":
    unittest.main()
