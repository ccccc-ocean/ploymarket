import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace

from ploymarket_sim.btc_price import BtcCandle
from ploymarket_sim.cli import _paper_position_state_signal
from ploymarket_sim.cli import _paper_position_signal_with_live_quote
from ploymarket_sim.cli import _paper_probe_trade_size_usdc
from ploymarket_sim.cli import _paper_reentry_edge_too_weak
from ploymarket_sim.cli import _fresh_paper_btc_candles
from ploymarket_sim.cli import _live_paper_entry_plan
from ploymarket_sim.cli import _market_discovery_is_healthy
from ploymarket_sim.cli import _paper_run_data_degraded
from ploymarket_sim.cli import _paper_markets_including_open_positions
from ploymarket_sim.cli import _paper_probe_available_slots
from ploymarket_sim.cli import _paper_probe_signal
from ploymarket_sim.cli import _positive_edge_blocked_market_types
from ploymarket_sim.cli import _realtime_market_discovery_is_healthy
from ploymarket_sim.cli import _strategy_loss_pause_blocks_entry
from ploymarket_sim.cli import _underperforming_probe_families
from ploymarket_sim.clob import PricePoint, TokenQuote
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


def standard_above_market() -> Market:
    return Market(
        "m1",
        "Will the price of Bitcoin be above $76,000 on June 3?",
        "btc-above-76000-jun-3",
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


def range_market() -> Market:
    return Market(
        "range-1",
        "Will the price of Bitcoin be between $70,000 and $72,000 on June 3?",
        "btc-between-70000-72000-jun-3",
        None,
        1000,
        100,
        True,
        ["Yes", "No"],
        [0.6, 0.4],
        ["range_yes", "range_no"],
        False,
        None,
        None,
    )


def touch_below_market() -> Market:
    return Market(
        "touch-below-1",
        "Will Bitcoin dip to $65,000 in June?",
        "bitcoin-dip-65000-june",
        None,
        1000,
        100,
        True,
        ["Yes", "No"],
        [0.7, 0.3],
        ["touch_yes", "touch_no"],
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

    def test_expired_resolved_position_is_settled_even_when_orderbook_is_available(self) -> None:
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

            expired_market = resolved_market(0.0, 1.0)
            with patch("ploymarket_sim.cli.get_token_quote", return_value=TokenQuote("no", bid=0.9, ask=0.91)) as quote_mock:
                with patch("ploymarket_sim.cli.get_market_by_id", return_value=expired_market):
                    signal = _paper_position_signal_with_live_quote(config, storage, expired_market, 0.0, 1780449901)

            self.assertIsNotNone(signal)
            assert signal is not None
            self.assertIn("按已解析结果结算", signal.reason)
            quote_mock.assert_not_called()
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

    def test_disabled_probe_family_open_position_is_risk_off_closed_with_live_bid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            config = AppConfig(
                config.api,
                config.cache,
                config.storage,
                config.btc_price,
                config.btc_filter,
                config.universe,
                config.signal,
                config.execution,
                config.risk,
                BacktestConfig(25.0, 0.0, 0, directory),
            )
            storage = Storage(True, config.storage.sqlite_path)
            self._write_run(
                Path(directory) / "paper_run_100.csv",
                [
                    [
                        "100",
                        "m1",
                        "above_below_expiry",
                        "Q",
                        "0.2",
                        "0.07",
                        "BUY_NO",
                        "0.1",
                        "0.2",
                        "0.1",
                        "过滤器挑战仓: 小仓位验证被 BTC regime 拦截",
                        "TAKER",
                        "BUY_NO",
                        "0.8",
                        "0.1",
                        "ok",
                    ]
                ],
            )
            storage.save_open_paper_position(
                PaperPositionState("m1", "NO", 0.8, 10.0, 8.0, 100, "open", None, 0.0, 0, 0.8, 0)
            )

            with patch("ploymarket_sim.cli.get_token_quote", return_value=TokenQuote("no", bid=0.7, ask=0.72)):
                signal = _paper_position_signal_with_live_quote(
                    config, storage, market(), yes_price=0.3, run_timestamp=200, disabled_probe_families={"regime_filter_challenge"}
                )

            self.assertIsNotNone(signal)
            assert signal is not None
            self.assertIn("risk-off 退出", signal.reason)
            position = storage.load_paper_position("m1")
            self.assertIsNotNone(position)
            assert position is not None
            self.assertEqual(position.status, "closed")
            self.assertAlmostEqual(position.realized_pnl, -1.0)

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

    def test_probe_does_not_override_strategy_loss_pause(self) -> None:
        config = app_config("unused.sqlite")
        history = [PricePoint(100 + index, 0.4) for index in range(config.signal.long_window)]
        paused_signal = Signal(
            "HOLD",
            0.0,
            0.2,
            0.2,
            "同类方向连续止损/亏损暂停: market_type=above_below_expiry, direction=above, side=NO, losses=2",
        )

        probe = _paper_probe_signal(config, market(), history, config, paused_signal, [])

        self.assertIsNone(probe)

    def test_regime_challenge_probe_blocks_when_near_strike_and_not_retreating(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        near_strike_market = Market(
            "near-1",
            "Will the price of Bitcoin be above $68,000 on June 3?",
            "btc-above-68000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.30, 0.70],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.30) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.12,
            0.12,
            "BTC regime=neutral 阻止 BUY_NO: BTC 已接近或站上 above strike，暂停逆突破方向",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67300.0, 67400.0, 67200.0, 67300.0),
            BtcCandle(timestamp - 900, 67470.0, 67500.0, 67420.0, 67470.0),
            BtcCandle(history[-1].timestamp, 67520.0, 67580.0, 67480.0, 67520.0),
        ]

        probe = _paper_probe_signal(config, near_strike_market, history, config, signal, candles)

        self.assertIsNone(probe)

    def test_regime_challenge_probe_can_open_when_far_from_strike(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.30) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.12,
            0.12,
            "BTC regime=downtrend 阻止 BUY_NO: BTC 已接近或站上 above strike，暂停逆突破方向",
        )
        candles = [
            BtcCandle(timestamp - 3600, 73000.0, 73100.0, 72900.0, 73000.0),
            BtcCandle(history[-1].timestamp, 73050.0, 73100.0, 73000.0, 73050.0),
        ]

        probe = _paper_probe_signal(config, standard_above_market(), history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("过滤器挑战仓", probe.reason)

    def test_underperforming_probe_family_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            config = AppConfig(
                config.api,
                config.cache,
                config.storage,
                config.btc_price,
                config.btc_filter,
                config.universe,
                config.signal,
                config.execution,
                config.risk,
                BacktestConfig(25.0, 0.0, 0, directory),
            )
            storage = Storage(True, config.storage.sqlite_path)
            self._write_run(
                Path(directory) / "paper_run_100.csv",
                [
                    ["100", "range-1", "range_bucket", "Q", "0.9", "0.07", "BUY_YES", "0.1", "0.2", "0.1", "探索仓: 连续零成交后，小仓位验证 range_bucket/YES", "TAKER", "BUY_YES", "0.9", "0.1", "ok"],
                    ["101", "range-2", "range_bucket", "Q", "0.9", "0.07", "BUY_YES", "0.1", "0.2", "0.1", "探索仓: 连续零成交后，小仓位验证 range_bucket/YES", "TAKER", "BUY_YES", "0.9", "0.1", "ok"],
                ],
            )
            for market_id, opened_at in [("range-1", 100), ("range-2", 101)]:
                storage.save_open_paper_position(
                    PaperPositionState(market_id, "YES", 0.9, 10.0, 9.0, opened_at, "open", None, 0.0, 0, 0.9, 0)
                )
                storage.close_paper_position(market_id, opened_at + 10, -1.0, opened_at + 100)

            disabled = _underperforming_probe_families(config, storage)

            self.assertIn("range_bucket_yes", disabled)

    def test_large_sample_negative_average_probe_family_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            config = AppConfig(
                config.api,
                config.cache,
                config.storage,
                config.btc_price,
                config.btc_filter,
                config.universe,
                config.signal,
                config.execution,
                config.risk,
                BacktestConfig(25.0, 0.0, 0, directory),
            )
            storage = Storage(True, config.storage.sqlite_path)
            rows = []
            for index in range(20):
                opened_at = 100 + index
                rows.append(
                    [
                        str(opened_at),
                        f"regime-{index}",
                        "above_below_expiry",
                        "Q",
                        "0.2",
                        "0.07",
                        "BUY_NO",
                        "0.1",
                        "0.2",
                        "0.1",
                        "过滤器挑战仓: 小仓位验证被 BTC regime 拦截",
                        "TAKER",
                        "BUY_NO",
                        "0.8",
                        "0.1",
                        "ok",
                    ]
                )
                storage.save_open_paper_position(
                    PaperPositionState(f"regime-{index}", "NO", 0.8, 4.0, 3.0, opened_at, "open", None, 0.0, 0, 0.8, 0)
                )
                storage.close_paper_position(f"regime-{index}", opened_at + 10, -0.01, opened_at + 100)
            self._write_run(Path(directory) / "paper_run_100.csv", rows)

            disabled = _underperforming_probe_families(config, storage)

            self.assertIn("regime_filter_challenge", disabled)

    def test_small_sample_moderate_negative_average_probe_family_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            config = AppConfig(
                config.api,
                config.cache,
                config.storage,
                config.btc_price,
                config.btc_filter,
                config.universe,
                config.signal,
                config.execution,
                config.risk,
                BacktestConfig(25.0, 0.0, 0, directory),
            )
            storage = Storage(True, config.storage.sqlite_path)
            rows = []
            for index in range(3):
                opened_at = 200 + index
                rows.append(
                    [
                        str(opened_at),
                        f"expensive-{index}",
                        "above_below_expiry",
                        "Q",
                        "0.2",
                        "0.07",
                        "BUY_NO",
                        "0.1",
                        "0.2",
                        "0.1",
                        "探索仓: 小仓位验证高价正edge above_below_expiry/NO",
                        "TAKER",
                        "BUY_NO",
                        "0.8",
                        "0.1",
                        "ok",
                    ]
                )
                storage.save_open_paper_position(
                    PaperPositionState(f"expensive-{index}", "NO", 0.8, 4.0, 3.0, opened_at, "open", None, 0.0, 0, 0.8, 0)
                )
                storage.close_paper_position(f"expensive-{index}", opened_at + 10, -0.06, opened_at + 100)
            self._write_run(Path(directory) / "paper_run_200.csv", rows)

            disabled = _underperforming_probe_families(config, storage)

            self.assertIn("expensive_edge_above_below_no", disabled)

    def test_single_large_probe_loss_disables_family(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            config = AppConfig(
                config.api,
                config.cache,
                config.storage,
                config.btc_price,
                config.btc_filter,
                config.universe,
                config.signal,
                config.execution,
                config.risk,
                BacktestConfig(25.0, 0.0, 0, directory),
            )
            storage = Storage(True, config.storage.sqlite_path)
            self._write_run(
                Path(directory) / "paper_run_300.csv",
                [
                    [
                        "300",
                        "touch-below-loss",
                        "touch_below",
                        "Q",
                        "0.2",
                        "0.07",
                        "BUY_NO",
                        "0.1",
                        "0.2",
                        "0.1",
                        "探索仓: 小仓位验证 touch_below/NO v1",
                        "TAKER",
                        "BUY_NO",
                        "0.8",
                        "0.1",
                        "ok",
                    ]
                ],
            )
            storage.save_open_paper_position(
                PaperPositionState("touch-below-loss", "NO", 0.8, 4.0, 3.0, 300, "open", None, 0.0, 0, 0.8, 0)
            )
            storage.close_paper_position("touch-below-loss", 310, -0.6, 400)

            disabled = _underperforming_probe_families(config, storage)

            self.assertIn("touch_below_no", disabled)

    def test_single_large_probe_loss_disables_family_even_when_total_pnl_is_positive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            config = AppConfig(
                config.api,
                config.cache,
                config.storage,
                config.btc_price,
                config.btc_filter,
                config.universe,
                config.signal,
                config.execution,
                config.risk,
                BacktestConfig(25.0, 0.0, 0, directory),
            )
            storage = Storage(True, config.storage.sqlite_path)
            self._write_run(
                Path(directory) / "paper_run_400.csv",
                [
                    [
                        "400",
                        "touch-below-win",
                        "touch_below",
                        "Q",
                        "0.4",
                        "0.07",
                        "BUY_YES",
                        "0.1",
                        "0.2",
                        "0.1",
                        "探索仓: 小仓位验证折扣 touch_below/YES v2",
                        "TAKER",
                        "BUY_YES",
                        "0.4",
                        "0.1",
                        "ok",
                    ],
                    [
                        "401",
                        "touch-below-loss",
                        "touch_below",
                        "Q",
                        "0.4",
                        "0.07",
                        "BUY_YES",
                        "0.1",
                        "0.2",
                        "0.1",
                        "探索仓: 小仓位验证折扣 touch_below/YES v2",
                        "TAKER",
                        "BUY_YES",
                        "0.4",
                        "0.1",
                        "ok",
                    ],
                ],
            )
            for market_id, opened_at, realized_pnl in [
                ("touch-below-win", 400, 0.9),
                ("touch-below-loss", 401, -0.6),
            ]:
                storage.save_open_paper_position(
                    PaperPositionState(market_id, "YES", 0.4, 7.5, 3.0, opened_at, "open", None, 0.0, 0, 0.4, 0)
                )
                storage.close_paper_position(market_id, opened_at + 10, realized_pnl, opened_at + 100)

            disabled = _underperforming_probe_families(config, storage)

            self.assertIn("touch_below_discount_yes", disabled)

    def test_range_center_probe_can_open_when_old_range_family_is_disabled(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.90) for index in range(config.signal.long_window)]
        signal = Signal("HOLD", 0.0, 0.08, 0.07, "当前市场类型暂不交易，只记录观察")
        candles = [
            BtcCandle(timestamp - 3600, 70950.0, 71100.0, 70900.0, 71000.0),
            BtcCandle(history[-1].timestamp, 70950.0, 71100.0, 70900.0, 71000.0),
        ]

        probe = _paper_probe_signal(config, range_market(), history, config, signal, candles, {"range_bucket_yes"})

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_YES")
        self.assertIn("区间中心 range_bucket/YES v1", probe.reason)
        self.assertEqual(_paper_probe_trade_size_usdc(config, probe), 1.0)

    def test_disabled_range_center_probe_does_not_open(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.90) for index in range(config.signal.long_window)]
        signal = Signal("HOLD", 0.0, 0.08, 0.07, "当前市场类型暂不交易，只记录观察")
        candles = [
            BtcCandle(timestamp - 3600, 70950.0, 71100.0, 70900.0, 71000.0),
            BtcCandle(history[-1].timestamp, 70950.0, 71100.0, 70900.0, 71000.0),
        ]

        probe = _paper_probe_signal(
            config,
            range_market(),
            history,
            config,
            signal,
            candles,
            {"range_bucket_yes", "range_bucket_center_yes"},
        )

        self.assertIsNone(probe)

    def test_expensive_positive_edge_no_probe_can_open_with_distance_buffer(self) -> None:
        config = app_config("unused.sqlite")
        history = [PricePoint(100 + index, 0.101) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.22,
            0.21,
            "range-like BUY_NO 价格过高，避免高价追 NO: no=0.899, max=0.750",
        )
        candles = [BtcCandle(history[-1].timestamp, 75000.0, 75100.0, 74950.0, 75000.0)]

        probe = _paper_probe_signal(config, standard_above_market(), history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("高价正edge above_below_expiry/NO", probe.reason)

    def test_disabled_expensive_positive_edge_no_probe_does_not_open(self) -> None:
        config = app_config("unused.sqlite")
        history = [PricePoint(100 + index, 0.101) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.22,
            0.21,
            "range-like BUY_NO 价格过高，避免高价追 NO: no=0.899, max=0.750",
        )
        candles = [BtcCandle(history[-1].timestamp, 75000.0, 75100.0, 74950.0, 75000.0)]

        probe = _paper_probe_signal(config, standard_above_market(), history, config, signal, candles, {"expensive_edge_above_below_no"})

        self.assertIsNone(probe)

    def test_certainty_above_below_yes_probe_can_open_when_btc_is_far_above_strike(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "yes-certainty",
            "Will the price of Bitcoin be above $66,000 on June 3?",
            "btc-above-66000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.86, 0.14],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.86) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.09,
            0.085,
            "above_below_expiry 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67800.0, 67900.0, 67700.0, 67800.0),
            BtcCandle(timestamp - 900, 67900.0, 68000.0, 67800.0, 67900.0),
            BtcCandle(history[-1].timestamp, 68000.0, 68100.0, 67900.0, 68000.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_YES")
        self.assertIn("高确定性 above_below_expiry/YES v1", probe.reason)

    def test_ultra_certainty_above_below_no_probe_can_open_as_micro_probe(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "no-ultra",
            "Will the price of Bitcoin be above $68,000 on June 3?",
            "btc-above-68000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.002, 0.998],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.002) for index in range(config.signal.long_window)]
        signal = Signal("HOLD", 0.0, 0.02, 0.012, "NO 价格太接近 1，盈亏比不够")
        candles = [
            BtcCandle(timestamp - 3600, 66700.0, 66800.0, 66600.0, 66700.0),
            BtcCandle(timestamp - 900, 66620.0, 66700.0, 66550.0, 66620.0),
            BtcCandle(history[-1].timestamp, 66600.0, 66700.0, 66500.0, 66600.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("超高确定性 above_below_expiry/NO v1", probe.reason)
        self.assertAlmostEqual(_paper_probe_trade_size_usdc(config, probe), 1.0)

    def test_ultra_certainty_above_below_no_probe_can_open_with_mid_high_no_price(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "no-ultra",
            "Will the price of Bitcoin be above $68,000 on June 3?",
            "btc-above-68000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.05, 0.95],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.05) for index in range(config.signal.long_window)]
        signal = Signal("HOLD", 0.0, 0.025, 0.019, "NO 价格太接近 1，盈亏比不够")
        candles = [
            BtcCandle(timestamp - 3600, 66950.0, 67050.0, 66850.0, 66950.0),
            BtcCandle(timestamp - 900, 66750.0, 66850.0, 66650.0, 66750.0),
            BtcCandle(history[-1].timestamp, 66600.0, 66700.0, 66500.0, 66600.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertAlmostEqual(_paper_probe_trade_size_usdc(config, probe), 1.0)

    def test_crossed_above_reversal_no_micro_probe_can_open_when_hourly_trend_weakens(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "crossed-no",
            "Will the price of Bitcoin be above $62,000 on June 3?",
            "btc-above-62000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.60, 0.40],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.60) for index in range(config.signal.long_window)]
        signal = Signal("BUY_NO", 1.0, 0.09, 0.06, "YES 动量转弱，NO 扣除成本后仍有正 edge")
        candles = [
            BtcCandle(timestamp - 3600, 62600.0, 62700.0, 62500.0, 62600.0),
            BtcCandle(timestamp - 900, 62180.0, 62220.0, 62150.0, 62180.0),
            BtcCandle(history[-1].timestamp, 62200.0, 62300.0, 62100.0, 62200.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("crossed-above 回落 above_below_expiry/NO v1", probe.reason)
        self.assertAlmostEqual(_paper_probe_trade_size_usdc(config, probe), 1.0)

    def test_crossed_above_reversal_no_micro_probe_blocks_when_breakout_accelerates(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "crossed-no",
            "Will the price of Bitcoin be above $62,000 on June 3?",
            "btc-above-62000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.60, 0.40],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.60) for index in range(config.signal.long_window)]
        signal = Signal("BUY_NO", 1.0, 0.09, 0.06, "YES 动量转弱，NO 扣除成本后仍有正 edge")
        candles = [
            BtcCandle(timestamp - 3600, 61700.0, 61800.0, 61600.0, 61700.0),
            BtcCandle(timestamp - 900, 62000.0, 62100.0, 61900.0, 62000.0),
            BtcCandle(history[-1].timestamp, 62400.0, 62500.0, 62300.0, 62400.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNone(probe)

    def test_crossed_above_reversal_no_micro_probe_can_recover_regime_blocked_buy_no(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "crossed-no",
            "Will the price of Bitcoin be above $62,000 on June 3?",
            "btc-above-62000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.60, 0.40],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.60) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.09,
            0.06,
            "BTC regime=volatile 阻止 BUY_NO: BTC 已接近或站上 above strike，暂停逆突破方向",
        )
        candles = [
            BtcCandle(timestamp - 3600, 62600.0, 62700.0, 62500.0, 62600.0),
            BtcCandle(timestamp - 900, 62180.0, 62220.0, 62150.0, 62180.0),
            BtcCandle(history[-1].timestamp, 62200.0, 62300.0, 62100.0, 62200.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("crossed-above 回落 above_below_expiry/NO v1", probe.reason)

    def test_ultra_certainty_above_below_no_probe_blocks_when_btc_rebounds_toward_strike(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "no-ultra",
            "Will the price of Bitcoin be above $68,000 on June 3?",
            "btc-above-68000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.002, 0.998],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.002) for index in range(config.signal.long_window)]
        signal = Signal("HOLD", 0.0, 0.02, 0.012, "NO 价格太接近 1，盈亏比不够")
        candles = [
            BtcCandle(timestamp - 3600, 65800.0, 65900.0, 65700.0, 65800.0),
            BtcCandle(timestamp - 900, 66300.0, 66400.0, 66200.0, 66300.0),
            BtcCandle(history[-1].timestamp, 66600.0, 66700.0, 66500.0, 66600.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNone(probe)

    def test_certainty_above_below_yes_probe_can_open_with_mid_price_and_clear_distance(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "yes-mid",
            "Will the price of Bitcoin be above $66,000 on June 4?",
            "btc-above-66000-jun-4",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.76, 0.24],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.76) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.04,
            0.035,
            "above_below_expiry 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67400.0, 67500.0, 67300.0, 67400.0),
            BtcCandle(timestamp - 900, 67600.0, 67700.0, 67500.0, 67600.0),
            BtcCandle(history[-1].timestamp, 68000.0, 68100.0, 67900.0, 68000.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_YES")
        self.assertIn("高确定性 above_below_expiry/YES v1", probe.reason)

    def test_certainty_above_below_yes_probe_blocks_when_btc_is_falling_toward_strike(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "yes-certainty",
            "Will the price of Bitcoin be above $66,000 on June 3?",
            "btc-above-66000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.86, 0.14],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.86) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.09,
            0.085,
            "above_below_expiry 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 68500.0, 68600.0, 68400.0, 68500.0),
            BtcCandle(timestamp - 900, 68100.0, 68200.0, 68000.0, 68100.0),
            BtcCandle(history[-1].timestamp, 68000.0, 68100.0, 67900.0, 68000.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNone(probe)

    def test_ultra_certainty_above_below_yes_probe_can_open_as_micro_probe(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "yes-ultra",
            "Will the price of Bitcoin be above $64,000 on June 4?",
            "btc-above-64000-jun-4",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.94, 0.06],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.94) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.03,
            0.022,
            "above_below_expiry 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67000.0, 67100.0, 66900.0, 67000.0),
            BtcCandle(timestamp - 900, 67100.0, 67200.0, 67000.0, 67100.0),
            BtcCandle(history[-1].timestamp, 67200.0, 67300.0, 67100.0, 67200.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_YES")
        self.assertIn("超高确定性 above_below_expiry/YES v1", probe.reason)
        self.assertAlmostEqual(_paper_probe_trade_size_usdc(config, probe), 1.0)

    def test_ultra_certainty_above_below_yes_probe_allows_mild_retreat_when_far_above_strike(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "yes-ultra",
            "Will the price of Bitcoin be above $64,000 on June 4?",
            "btc-above-64000-jun-4",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.915, 0.085],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.915) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.025,
            0.018,
            "above_below_expiry 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67000.0, 67100.0, 66900.0, 67000.0),
            BtcCandle(timestamp - 900, 66800.0, 66900.0, 66700.0, 66800.0),
            BtcCandle(history[-1].timestamp, 66680.0, 66750.0, 66600.0, 66680.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_YES")
        self.assertAlmostEqual(_paper_probe_trade_size_usdc(config, probe), 1.0)

    def test_ultra_certainty_above_below_yes_probe_blocks_when_btc_is_retreating(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        market = Market(
            "yes-ultra",
            "Will the price of Bitcoin be above $64,000 on June 4?",
            "btc-above-64000-jun-4",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.94, 0.06],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.94) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.03,
            0.022,
            "above_below_expiry 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 68100.0, 68200.0, 68000.0, 68100.0),
            BtcCandle(timestamp - 900, 67800.0, 67900.0, 67700.0, 67800.0),
            BtcCandle(history[-1].timestamp, 67200.0, 67300.0, 67100.0, 67200.0),
        ]

        probe = _paper_probe_signal(config, market, history, config, signal, candles)

        self.assertIsNone(probe)

    def test_strategy_review_positive_edge_blocked_types_are_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "strategy_review.csv").write_text(
                "\n".join(
                    [
                        "market_type,status,recommended_action,reason,taker_count,probe_taker_count,positive_edge_skip_count,max_expected_edge,top_blocker",
                        "above_below_expiry,positive_edge_blocked,allow,reason,0,0,42,0.08,type_side_not_enabled:42/42",
                        "touch_above,edge_insufficient,hold,reason,0,0,42,0.08,type_side_not_enabled:42/42",
                        "range_bucket,positive_edge_blocked,allow,reason,0,0,2,0.08,type_side_not_enabled:2/2",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            blocked = _positive_edge_blocked_market_types(directory)

            self.assertEqual(blocked, {"above_below_expiry"})

    def test_blocked_edge_above_below_yes_micro_probe_uses_strategy_review_context(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        blocked_market = Market(
            "blocked-yes",
            "Will the price of Bitcoin be above $66,000 on June 4?",
            "btc-above-66000-jun-4",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.88, 0.12],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.88) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.09,
            0.08,
            "above_below_expiry 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67400.0, 67500.0, 67300.0, 67400.0),
            BtcCandle(timestamp - 900, 67500.0, 67600.0, 67400.0, 67500.0),
            BtcCandle(history[-1].timestamp, 67600.0, 67700.0, 67500.0, 67600.0),
        ]

        probe = _paper_probe_signal(
            config,
            blocked_market,
            history,
            config,
            signal,
            candles,
            {"above_below_yes", "certainty_above_below_yes", "ultra_certainty_above_below_yes"},
            {"above_below_expiry"},
        )

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_YES")
        self.assertIn("报告阻塞正edge above_below_expiry/YES v1", probe.reason)
        self.assertAlmostEqual(_paper_probe_trade_size_usdc(config, probe), 1.0)

    def test_blocked_edge_above_below_yes_micro_probe_requires_strategy_review_context(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        blocked_market = Market(
            "blocked-yes",
            "Will the price of Bitcoin be above $66,000 on June 4?",
            "btc-above-66000-jun-4",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.88, 0.12],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.88) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.09,
            0.08,
            "above_below_expiry 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67400.0, 67500.0, 67300.0, 67400.0),
            BtcCandle(history[-1].timestamp, 67600.0, 67700.0, 67500.0, 67600.0),
        ]

        probe = _paper_probe_signal(
            config,
            blocked_market,
            history,
            config,
            signal,
            candles,
            {"above_below_yes", "certainty_above_below_yes", "ultra_certainty_above_below_yes"},
        )

        self.assertIsNone(probe)

    def test_recovery_above_below_no_probe_can_open_with_wide_strike_buffer(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.10) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.12,
            0.105,
            "range-like BUY_NO 价格过高，避免高价追 NO: no=0.900, max=0.750",
        )
        candles = [
            BtcCandle(timestamp - 3600, 74200.0, 74300.0, 74100.0, 74200.0),
            BtcCandle(timestamp - 900, 74100.0, 74200.0, 74000.0, 74100.0),
            BtcCandle(history[-1].timestamp, 74000.0, 74100.0, 73900.0, 74000.0),
        ]

        probe = _paper_probe_signal(config, standard_above_market(), history, config, signal, candles, {"expensive_edge_above_below_no"})

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("样本恢复 above_below_expiry/NO v1", probe.reason)

    def test_recovery_above_below_no_probe_blocks_when_btc_is_rising_toward_strike(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.10) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.12,
            0.105,
            "range-like BUY_NO 价格过高，避免高价追 NO: no=0.900, max=0.750",
        )
        candles = [
            BtcCandle(timestamp - 3600, 73600.0, 73700.0, 73500.0, 73600.0),
            BtcCandle(timestamp - 900, 73800.0, 73900.0, 73700.0, 73800.0),
            BtcCandle(history[-1].timestamp, 74000.0, 74100.0, 73900.0, 74000.0),
        ]

        probe = _paper_probe_signal(config, standard_above_market(), history, config, signal, candles, {"expensive_edge_above_below_no"})

        self.assertIsNone(probe)

    def test_near_strike_no_probe_can_open_when_btc_is_retreating_from_strike(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        near_strike_market = Market(
            "near-1",
            "Will the price of Bitcoin be above $68,000 on June 3?",
            "btc-above-68000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.384, 0.616],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.384) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.25,
            0.24,
            "BTC 未明显远离 above strike，暂停 BUY_NO: BTC=67480.00, strike=68000.00, distance=0.77%, 15m=-0.23%",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67900.0, 68000.0, 67800.0, 67900.0),
            BtcCandle(timestamp - 900, 67640.0, 67700.0, 67550.0, 67640.0),
            BtcCandle(history[-1].timestamp, 67480.0, 67520.0, 67400.0, 67480.0),
        ]

        probe = _paper_probe_signal(config, near_strike_market, history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("near-strike 安全带 above_below_expiry/NO", probe.reason)

    def test_near_strike_no_probe_blocks_when_btc_is_not_retreating_from_strike(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        near_strike_market = Market(
            "near-1",
            "Will the price of Bitcoin be above $68,000 on June 3?",
            "btc-above-68000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.384, 0.616],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.384) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.25,
            0.24,
            "BTC 未明显远离 above strike，暂停 BUY_NO: BTC=67480.00, strike=68000.00, distance=0.77%, 15m=0.03%",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67400.0, 67500.0, 67300.0, 67400.0),
            BtcCandle(timestamp - 900, 67460.0, 67500.0, 67400.0, 67460.0),
            BtcCandle(history[-1].timestamp, 67480.0, 67520.0, 67400.0, 67480.0),
        ]

        probe = _paper_probe_signal(config, near_strike_market, history, config, signal, candles)

        self.assertIsNone(probe)

    def test_disabled_near_strike_no_probe_does_not_open(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        near_strike_market = Market(
            "near-1",
            "Will the price of Bitcoin be above $68,000 on June 3?",
            "btc-above-68000-jun-3",
            None,
            1000,
            100,
            True,
            ["Yes", "No"],
            [0.384, 0.616],
            ["yes", "no"],
            False,
            None,
            None,
        )
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.384) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.25,
            0.24,
            "BTC 正接近 above strike，暂停 BUY_NO: BTC=67480.00, strike=68000.00, distance=0.77%, 15m=0.23%",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67300.0, 67400.0, 67200.0, 67300.0),
            BtcCandle(history[-1].timestamp, 67480.0, 67520.0, 67400.0, 67480.0),
        ]

        probe = _paper_probe_signal(
            config,
            near_strike_market,
            history,
            config,
            signal,
            candles,
            {"near_strike_above_below_no"},
        )

        self.assertIsNone(probe)

    def test_touch_below_no_probe_can_open_when_no_side_has_strict_confirmation(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.10) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.11,
            0.10,
            "touch_below 暂不允许 BUY_NO，当前结构先观察不交易",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67200.0, 67300.0, 67100.0, 67200.0),
            BtcCandle(timestamp - 900, 67240.0, 67300.0, 67200.0, 67250.0),
            BtcCandle(history[-1].timestamp, 67250.0, 67300.0, 67200.0, 67250.0),
        ]

        probe = _paper_probe_signal(config, touch_below_market(), history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("touch_below/NO v1", probe.reason)

    def test_disabled_touch_below_no_probe_does_not_open(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.10) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.11,
            0.10,
            "touch_below 暂不允许 BUY_NO，当前结构先观察不交易",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67200.0, 67300.0, 67100.0, 67200.0),
            BtcCandle(history[-1].timestamp, 67250.0, 67300.0, 67200.0, 67250.0),
        ]

        probe = _paper_probe_signal(
            config,
            touch_below_market(),
            history,
            config,
            signal,
            candles,
            {"touch_below_no"},
        )

        self.assertIsNone(probe)

    def test_touch_below_certainty_no_probe_can_open_when_target_is_safe_and_btc_not_falling(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.037) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.045,
            0.038,
            "touch_below 暂不允许 BUY_NO，当前结构先观察不交易",
        )
        candles = [
            BtcCandle(timestamp - 3600, 66700.0, 66850.0, 66600.0, 66700.0),
            BtcCandle(timestamp - 900, 66800.0, 66900.0, 66700.0, 66800.0),
            BtcCandle(history[-1].timestamp, 66817.0, 66900.0, 66750.0, 66817.0),
        ]

        probe = _paper_probe_signal(config, touch_below_market(), history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("高确定性 touch_below/NO v2", probe.reason)

    def test_touch_below_certainty_no_probe_blocks_when_btc_is_falling_toward_target(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.037) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.045,
            0.038,
            "touch_below 暂不允许 BUY_NO，当前结构先观察不交易",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67100.0, 67200.0, 67000.0, 67100.0),
            BtcCandle(timestamp - 900, 66950.0, 67000.0, 66800.0, 66950.0),
            BtcCandle(history[-1].timestamp, 66817.0, 66900.0, 66750.0, 66817.0),
        ]

        probe = _paper_probe_signal(config, touch_below_market(), history, config, signal, candles)

        self.assertIsNone(probe)

    def test_disabled_touch_below_certainty_no_probe_does_not_open(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.037) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.045,
            0.038,
            "touch_below 暂不允许 BUY_NO，当前结构先观察不交易",
        )
        candles = [
            BtcCandle(timestamp - 3600, 66700.0, 66850.0, 66600.0, 66700.0),
            BtcCandle(timestamp - 900, 66800.0, 66900.0, 66700.0, 66800.0),
            BtcCandle(history[-1].timestamp, 66817.0, 66900.0, 66750.0, 66817.0),
        ]

        probe = _paper_probe_signal(
            config,
            touch_below_market(),
            history,
            config,
            signal,
            candles,
            {"touch_below_certainty_no"},
        )

        self.assertIsNone(probe)

    def test_touch_below_distance_no_micro_probe_can_open_from_positive_edge_skip(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.55) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.055,
            0.045,
            "净优势不足，等待更清晰的定价偏差",
        )
        candles = [
            BtcCandle(timestamp - 3600, 70100.0, 70200.0, 70000.0, 70100.0),
            BtcCandle(timestamp - 900, 70200.0, 70300.0, 70100.0, 70200.0),
            BtcCandle(history[-1].timestamp, 70300.0, 70400.0, 70200.0, 70300.0),
        ]

        probe = _paper_probe_signal(config, touch_below_market(), history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("距离安全 touch_below/NO v1", probe.reason)

    def test_touch_below_distance_no_micro_probe_can_open_from_type_side_observation(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.412) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.068,
            0.058,
            "touch_below 暂不允许 BUY_NO，当前结构先观察不交易",
        )
        candles = [
            BtcCandle(timestamp - 3600, 69000.0, 69100.0, 68900.0, 69000.0),
            BtcCandle(timestamp - 900, 69600.0, 69700.0, 69500.0, 69600.0),
            BtcCandle(history[-1].timestamp, 69500.0, 69600.0, 69400.0, 69500.0),
        ]

        probe = _paper_probe_signal(config, touch_below_market(), history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_NO")
        self.assertIn("距离安全 touch_below/NO v1", probe.reason)

    def test_touch_below_distance_no_micro_probe_blocks_when_btc_falls_toward_target(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.55) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.055,
            0.045,
            "净优势不足，等待更清晰的定价偏差",
        )
        candles = [
            BtcCandle(timestamp - 3600, 71000.0, 71100.0, 70900.0, 71000.0),
            BtcCandle(timestamp - 900, 70700.0, 70800.0, 70600.0, 70700.0),
            BtcCandle(history[-1].timestamp, 70300.0, 70400.0, 70200.0, 70300.0),
        ]

        probe = _paper_probe_signal(config, touch_below_market(), history, config, signal, candles)

        self.assertIsNone(probe)

    def test_touch_below_momentum_yes_probe_can_open_with_downward_confirmation(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.48) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.24,
            0.22,
            "touch_below 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67400.0, 67500.0, 67300.0, 67400.0),
            BtcCandle(timestamp - 900, 67250.0, 67300.0, 67150.0, 67250.0),
            BtcCandle(history[-1].timestamp, 67000.0, 67100.0, 66900.0, 67000.0),
        ]

        probe = _paper_probe_signal(config, touch_below_market(), history, config, signal, candles)

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_YES")
        self.assertIn("touch_below/YES momentum v1", probe.reason)

    def test_disabled_touch_below_momentum_yes_probe_does_not_open(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.48) for index in range(config.signal.long_window)]
        signal = Signal(
            "HOLD",
            0.0,
            0.24,
            0.22,
            "touch_below 暂不允许 BUY_YES，避免把高噪音结构硬套方向多单",
        )
        candles = [
            BtcCandle(timestamp - 3600, 67400.0, 67500.0, 67300.0, 67400.0),
            BtcCandle(history[-1].timestamp, 67000.0, 67100.0, 66900.0, 67000.0),
        ]

        probe = _paper_probe_signal(
            config,
            touch_below_market(),
            history,
            config,
            signal,
            candles,
            {"touch_below_momentum_yes"},
        )

        self.assertIsNone(probe)

    def test_touch_below_discount_probe_can_open_even_when_old_touch_probe_is_disabled(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.70) for index in range(config.signal.long_window)]
        signal = Signal("HOLD", 0.0, 0.05, 0.045, "净优势不足，等待更清晰的定价偏差")
        candles = [
            BtcCandle(timestamp - 3600, 67200.0, 67300.0, 67100.0, 67200.0),
            BtcCandle(history[-1].timestamp, 67000.0, 67100.0, 66900.0, 67000.0),
        ]

        probe = _paper_probe_signal(config, touch_below_market(), history, config, signal, candles, {"touch_below_yes"})

        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe.action, "BUY_YES")
        self.assertIn("折扣 touch_below/YES v2", probe.reason)

    def test_disabled_touch_below_discount_probe_does_not_open(self) -> None:
        config = app_config("unused.sqlite")
        timestamp = 7200
        history = [PricePoint(timestamp - config.signal.long_window + index + 1, 0.70) for index in range(config.signal.long_window)]
        signal = Signal("HOLD", 0.0, 0.05, 0.045, "净优势不足，等待更清晰的定价偏差")
        candles = [
            BtcCandle(timestamp - 3600, 67200.0, 67300.0, 67100.0, 67200.0),
            BtcCandle(history[-1].timestamp, 67000.0, 67100.0, 66900.0, 67000.0),
        ]

        probe = _paper_probe_signal(
            config,
            touch_below_market(),
            history,
            config,
            signal,
            candles,
            {"touch_below_discount_yes"},
        )

        self.assertIsNone(probe)

    def test_probe_slots_can_expand_when_soft_count_is_full_but_exposure_is_small(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            config = AppConfig(
                config.api,
                config.cache,
                config.storage,
                config.btc_price,
                config.btc_filter,
                config.universe,
                config.signal,
                config.execution,
                config.risk,
                BacktestConfig(25.0, 0.0, 0, directory),
            )
            config = replace(config, risk=replace(config.risk, paper_probe_zero_run_threshold=1, paper_probe_trade_size_usdc=3.0))
            storage = Storage(True, config.storage.sqlite_path)
            self._write_paper_report(Path(directory) / "paper_report.csv", taker_count=0)
            self._write_probe_run(Path(directory) / "paper_run_100.csv", "probe-", config.risk.paper_probe_max_open_positions)
            for index in range(config.risk.paper_probe_max_open_positions):
                storage.save_open_paper_position(
                    PaperPositionState(
                        f"probe-{index}",
                        "NO",
                        0.95,
                        3.0,
                        3.0,
                        100 + index,
                        "open",
                        None,
                        0.0,
                        0,
                        0.95,
                        0,
                    )
                )

            self.assertGreater(_paper_probe_available_slots(config, storage), 0)

    def test_probe_slots_stop_at_exposure_budget_even_below_hard_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            config = AppConfig(
                config.api,
                config.cache,
                config.storage,
                config.btc_price,
                config.btc_filter,
                config.universe,
                config.signal,
                config.execution,
                config.risk,
                BacktestConfig(25.0, 0.0, 0, directory),
            )
            config = replace(config, risk=replace(config.risk, paper_probe_zero_run_threshold=1, paper_probe_trade_size_usdc=3.0))
            storage = Storage(True, config.storage.sqlite_path)
            self._write_paper_report(Path(directory) / "paper_report.csv", taker_count=0)
            self._write_probe_run(Path(directory) / "paper_run_100.csv", "probe-", config.risk.paper_probe_max_open_positions)
            for index in range(config.risk.paper_probe_max_open_positions):
                storage.save_open_paper_position(
                    PaperPositionState(
                        f"probe-{index}",
                        "NO",
                        0.95,
                        10.0,
                        6.0,
                        100 + index,
                        "open",
                        None,
                        0.0,
                        0,
                        0.95,
                        0,
                    )
                )

            self.assertEqual(_paper_probe_available_slots(config, storage), 0)

    def test_normal_open_position_does_not_consume_probe_exposure_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = app_config(str(Path(directory) / "paper.sqlite"))
            config = AppConfig(
                config.api,
                config.cache,
                config.storage,
                config.btc_price,
                config.btc_filter,
                config.universe,
                config.signal,
                config.execution,
                config.risk,
                BacktestConfig(25.0, 0.0, 0, directory),
            )
            config = replace(config, risk=replace(config.risk, paper_probe_zero_run_threshold=1, paper_probe_trade_size_usdc=3.0))
            storage = Storage(True, config.storage.sqlite_path)
            self._write_paper_report(Path(directory) / "paper_report.csv", taker_count=0)
            self._write_probe_run(Path(directory) / "paper_run_100.csv", "probe-", config.risk.paper_probe_max_open_positions)
            for index in range(config.risk.paper_probe_max_open_positions):
                storage.save_open_paper_position(
                    PaperPositionState(f"probe-{index}", "NO", 0.95, 3.0, 3.0, 100 + index, "open", None, 0.0, 0, 0.95, 0)
                )
            storage.save_open_paper_position(
                PaperPositionState("normal-main", "NO", 0.65, 40.0, 25.0, 999, "open", None, 0.0, 0, 0.65, 0)
            )

            self.assertGreater(_paper_probe_available_slots(config, storage), 0)

    def _write_run(self, path: Path, rows: list[list[str]]) -> None:
        path.write_text(
            "\n".join(
                [
                    "run_timestamp,market_id,market_type,question,yes_price,taker_fee_rate,action,confidence,gross_edge,net_edge,reason,execution_mode,execution_side,limit_price,expected_net_edge,execution_reason",
                    *[",".join(row) for row in rows],
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_paper_report(self, path: Path, taker_count: int) -> None:
        path.write_text(
            "run_timestamp,markets,buy_yes,buy_no,hold,avoid,taker_count,maker_count,skip_count,top_market_id,top_market_type,top_net_edge,top_action,top_execution_mode,top_question\n"
            f"1,1,0,0,1,0,{taker_count},0,1,m1,above_below_expiry,0,HOLD,SKIP,Q\n",
            encoding="utf-8",
        )

    def _write_probe_run(self, path: Path, market_prefix: str, count: int) -> None:
        rows = []
        for index in range(count):
            rows.append(
                [
                    str(100 + index),
                    f"{market_prefix}{index}",
                    "above_below_expiry",
                    "Q",
                    "0.2",
                    "0.07",
                    "BUY_NO",
                    "0.1",
                    "0.2",
                    "0.1",
                    "探索仓: sample",
                    "TAKER",
                    "BUY_NO",
                    "0.8",
                    "0.1",
                    "ok",
                ]
            )
        self._write_run(path, rows)

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
