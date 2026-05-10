import unittest

from ploymarket_sim.btc_price import _parse_coinbase_candle


class BtcPriceTests(unittest.TestCase):
    def test_parses_coinbase_candle(self) -> None:
        candle = _parse_coinbase_candle([1778400000, "100.0", "110.0", "101.0", "108.0"])

        self.assertIsNotNone(candle)
        self.assertEqual(candle.timestamp, 1778400000)
        self.assertEqual(candle.low, 100.0)
        self.assertEqual(candle.high, 110.0)
        self.assertEqual(candle.open, 101.0)
        self.assertEqual(candle.close, 108.0)

    def test_skips_invalid_candle(self) -> None:
        self.assertIsNone(_parse_coinbase_candle(["bad"]))

    def test_parses_coinbase_public_candle_dict(self) -> None:
        candle = _parse_coinbase_candle(
            {"start": "1778400000", "low": "100.0", "high": "110.0", "open": "101.0", "close": "108.0"}
        )

        self.assertIsNotNone(candle)
        self.assertEqual(candle.close, 108.0)
