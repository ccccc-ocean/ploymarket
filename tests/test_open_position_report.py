import tempfile
import unittest
from pathlib import Path

from ploymarket_sim.open_position_report import build_open_position_report, write_open_position_report_csv
from ploymarket_sim.polymarket import Market
from ploymarket_sim.storage import PaperPositionState


def market(end_date="2026-06-03T16:00:00Z") -> Market:
    return Market(
        "m1",
        "Will the price of Bitcoin be above $72,000 on June 3?",
        "btc-above-72000-jun-3",
        end_date,
        1000,
        100,
        True,
        ["Yes", "No"],
        [0.2, 0.8],
        ["yes-token", "no-token"],
        False,
        None,
        None,
    )


class OpenPositionReportTests(unittest.TestCase):
    def test_builds_open_position_report_with_probe_family_and_live_pnl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "paper_run_100.csv").write_text(
                "\n".join(
                    [
                        "run_timestamp,market_id,market_type,question,yes_price,taker_fee_rate,action,confidence,gross_edge,net_edge,reason,execution_mode,execution_side,limit_price,expected_net_edge,execution_reason",
                        "100,m1,above_below_expiry,Q,0.2,0.07,BUY_NO,0.1,0.2,0.1,过滤器挑战仓: 小仓位验证被 BTC regime 拦截,TAKER,BUY_NO,0.8,0.1,ok",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            position = PaperPositionState("m1", "NO", 0.7, 10.0, 7.0, 100, "open", None, 0.25, 0, 0.7, 1)

            rows = build_open_position_report(directory, [market()], [position], 101, {"m1": 0.8})

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.market_type, "above_below_expiry")
            self.assertEqual(row.probe_family, "regime_filter_challenge")
            self.assertEqual(row.current_price_source, "live_bid")
            self.assertAlmostEqual(row.unrealized_pnl or 0.0, 1.0)
            self.assertAlmostEqual(row.estimated_total_pnl or 0.0, 1.25)
            self.assertEqual(row.expiry_status, "pre_expiry")
            self.assertEqual(row.partial_take_profit_count, 1)

    def test_marks_expired_position_as_pending_settlement(self) -> None:
        position = PaperPositionState("m1", "YES", 0.4, 10.0, 4.0, 100, "open", None, 0.0, 0, 0.4, 0)

        rows = build_open_position_report(
            "missing-output-dir",
            [market("2026-06-03T04:00:00Z")],
            [position],
            1780470000,
            {},
        )

        self.assertEqual(rows[0].expiry_status, "expired_pending_settlement")
        self.assertEqual(rows[0].current_price_source, "stored_market_price")

    def test_writes_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            position = PaperPositionState("m1", "NO", 0.7, 10.0, 7.0, 100, "open", None, 0.0, 0, 0.7, 0)
            rows = build_open_position_report(directory, [market()], [position], 101, {})

            path = write_open_position_report_csv(rows, directory)

            self.assertTrue(path.exists())
            self.assertIn("open_position_report.csv", path.name)


if __name__ == "__main__":
    unittest.main()
