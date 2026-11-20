import unittest

from tillpoint import db
from tillpoint.api import App


class PaymentRetryTest(unittest.TestCase):
    """Report 1: the provider retries a webhook until it gets a 2xx, so the same event can arrive many times."""

    def setUp(self):
        self.conn = db.connect()
        self.app = App(self.conn)
        self.app.catalog.add_product("MUG", "Mug", 1200, stock=10)

    def event(self, order_id, event_id="evt_1", amount=1200):
        return {"id": event_id, "type": "payment.succeeded", "order_id": order_id, "amount_cents": amount}

    def test_retried_event_is_counted_once(self):
        order = self.app.orders.create("ana", [("MUG", 1)])
        for _ in range(3):
            self.app.handle("POST", "/webhooks/payments", self.event(order["id"]))
        self.assertEqual(self.app.payments.paid_cents(order["id"]), 1200)

    def test_retried_event_keeps_reporting_the_order_status(self):
        order = self.app.orders.create("ana", [("MUG", 1)])
        first = self.app.handle("POST", "/webhooks/payments", self.event(order["id"]))
        again = self.app.handle("POST", "/webhooks/payments", self.event(order["id"]))
        self.assertEqual(first, (200, {"status": "paid"}))
        self.assertEqual(again, (200, {"status": "paid"}))

    def test_two_different_events_are_both_recorded(self):
        order = self.app.orders.create("ana", [("MUG", 1)])
        self.app.payments.handle_event(self.event(order["id"], "evt_a"))
        self.app.payments.handle_event(self.event(order["id"], "evt_b"))
        self.assertEqual(self.app.payments.paid_cents(order["id"]), 2400)


if __name__ == "__main__":
    unittest.main()
