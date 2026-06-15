import unittest

from ploymarket_sim.risk import Portfolio, Position, approve_entry, should_exit
from ploymarket_sim.config import RiskConfig


def risk_config() -> RiskConfig:
    return RiskConfig(
        starting_cash=1000.0,
        max_position_usdc=50.0,
        max_market_exposure_usdc=75.0,
        max_total_exposure_usdc=100.0,
        max_open_positions=2,
        daily_loss_limit_usdc=25.0,
        max_drawdown_pct=0.1,
        stop_loss_pct=0.25,
        take_profit_pct=0.35,
        max_spread=0.08,
        min_price=0.03,
        max_price=0.97,
    )


class RiskTests(unittest.TestCase):
    def test_rejects_position_above_limit(self) -> None:
        decision = approve_entry(Portfolio.from_starting_cash(1000), risk_config(), "m1", 0.5, 75.0)
        self.assertFalse(decision.approved)
        self.assertIn("单笔仓位", decision.reason)

    def test_allows_small_trade(self) -> None:
        decision = approve_entry(Portfolio.from_starting_cash(1000), risk_config(), "m1", 0.5, 25.0)
        self.assertTrue(decision.approved)

    def test_fixed_usdc_stop_loss_overrides_percentage_exit(self) -> None:
        config = risk_config()
        config = RiskConfig(**{**config.__dict__, "stop_loss_usdc": 10.0, "take_profit_usdc": 20.0})
        position = Position("m1", "yes", 0.5, 60.0, 30.0)

        exit_now, reason = should_exit(position, 0.40, config, estimated_pnl_usdc=-10.0)

        self.assertTrue(exit_now)
        self.assertIn("USDC 固定止损", reason)

    def test_fixed_usdc_take_profit_overrides_percentage_exit(self) -> None:
        config = risk_config()
        config = RiskConfig(**{**config.__dict__, "stop_loss_usdc": 10.0, "take_profit_usdc": 20.0})
        position = Position("m1", "yes", 0.5, 60.0, 30.0)

        exit_now, reason = should_exit(position, 0.84, config, estimated_pnl_usdc=20.0)

        self.assertTrue(exit_now)
        self.assertIn("USDC 固定止盈", reason)
