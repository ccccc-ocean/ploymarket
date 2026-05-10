import unittest

from ploymarket_sim.orders import lifecycle_events, make_order_id, rejected_events


class OrderTests(unittest.TestCase):
    def test_lifecycle_events_follow_happy_path(self) -> None:
        events = lifecycle_events(1, "o1", "m1", "buy_yes", 0.5, 25.0, "signal")

        self.assertEqual([event.status for event in events], ["created", "submitted", "accepted", "matched", "settled"])

    def test_rejected_events_stop_at_rejected(self) -> None:
        events = rejected_events(1, "o1", "m1", "buy_yes", 0.5, 25.0, "risk")

        self.assertEqual([event.status for event in events], ["created", "rejected"])

    def test_order_id_is_stable(self) -> None:
        self.assertEqual(make_order_id("m1", 123, 2), "m1-123-2")
