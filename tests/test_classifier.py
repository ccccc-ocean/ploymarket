import unittest

from ploymarket_sim.classifier import classify_market
from ploymarket_sim.polymarket import Market


def market(question: str, slug: str = "btc") -> Market:
    return Market("1", question, slug, None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)


class ClassifierTests(unittest.TestCase):
    def test_classifies_price_target_market(self) -> None:
        self.assertEqual(classify_market(market("Will Bitcoin reach $100,000 in May?")).market_type, "touch_above")

    def test_classifies_daily_price_target_market(self) -> None:
        self.assertEqual(classify_market(market("Will Bitcoin reach $84,000 on May 19?")).market_type, "expiry_target")

    def test_classifies_daily_price_range_market(self) -> None:
        self.assertEqual(
            classify_market(market("Will the price of Bitcoin be above $80,000 on May 8?")).market_type,
            "above_below_expiry",
        )

    def test_classifies_up_down_market(self) -> None:
        self.assertEqual(classify_market(market("Bitcoin Up or Down on May 8?")).market_type, "up_down_short_term")

    def test_classifies_range_bucket_market(self) -> None:
        self.assertEqual(
            classify_market(market("Will the price of Bitcoin be between $74,000 and $76,000 on May 30?")).market_type,
            "range_bucket",
        )

    def test_classifies_touch_below_market(self) -> None:
        self.assertEqual(classify_market(market("Will Bitcoin dip to $72,500 in May?")).market_type, "touch_below")

    def test_classifies_company_treasury_market(self) -> None:
        self.assertEqual(
            classify_market(market("MicroStrategy sells any Bitcoin by December 31, 2026?")).market_type,
            "company_treasury",
        )

    def test_classifies_indirect_event_market(self) -> None:
        self.assertEqual(classify_market(market("Will Anthropic flip BTC by December 31?")).market_type, "indirect_event")
