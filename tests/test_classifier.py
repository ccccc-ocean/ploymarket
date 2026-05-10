import unittest

from ploymarket_sim.classifier import classify_market
from ploymarket_sim.polymarket import Market


def market(question: str, slug: str = "btc") -> Market:
    return Market("1", question, slug, None, 1000, 1000, True, ["Yes", "No"], [0.5, 0.5], ["yes", "no"], False, None, None)


class ClassifierTests(unittest.TestCase):
    def test_classifies_price_target_market(self) -> None:
        self.assertEqual(classify_market(market("Will Bitcoin reach $100,000 in May?")).market_type, "price_target")

    def test_classifies_daily_price_range_market(self) -> None:
        self.assertEqual(
            classify_market(market("Will the price of Bitcoin be above $80,000 on May 8?")).market_type,
            "price_range_daily",
        )

    def test_classifies_company_treasury_market(self) -> None:
        self.assertEqual(
            classify_market(market("MicroStrategy sells any Bitcoin by December 31, 2026?")).market_type,
            "company_treasury",
        )

    def test_classifies_indirect_event_market(self) -> None:
        self.assertEqual(classify_market(market("Will Anthropic flip BTC by December 31?")).market_type, "indirect_event")
