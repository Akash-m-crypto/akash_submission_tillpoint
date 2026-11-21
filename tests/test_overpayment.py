import unittest

from tillpoint import db, reports
from tillpoint.api import App


class OverpaymentTest(unittest.TestCase):
    """Report 6: a customer can really pay twice (two different events). We keep both payments and flag the excess."""

    def setUp(self):
        self.app = App(db.connect())
        self.app.catalog.add_product("MUG", "Mug", 1200, stock=10)
        self.order = self.app.orders.create("ana", [("MUG", 1)])

    def pay(self, event_id, amount):
        self.app.payments.handle_event(
            {"id": event_id, "type": "payment.succeeded", "order_id": self.order["id"], "amount_cents": amount})

    def get(self):
        return self.app.orders.get(self.order["id"])

    def test_exact_payment_is_not_overpaid(self):
        self.pay("evt_1", 1200)
        self.assertEqual(self.get()["overpaid_cents"], 0)

    def test_two_partial_payments_that_add_up_are_not_overpaid(self):
        self.pay("evt_1", 500)
        self.pay("evt_2", 700)
        order = self.get()
        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["overpaid_cents"], 0)

    def test_paying_twice_keeps_both_payments_and_shows_the_excess(self):
        self.pay("evt_1", 1200)
        self.pay("evt_2", 1200)
        order = self.get()
        self.assertEqual(order["paid_cents"], 2400)
        self.assertEqual(order["overpaid_cents"], 1200)
        self.assertEqual(order["status"], "paid")

    def test_retry_of_the_second_payment_does_not_grow_the_excess(self):
        self.pay("evt_1", 1200)
        self.pay("evt_2", 1200)
        self.pay("evt_2", 1200)
        self.assertEqual(self.get()["overpaid_cents"], 1200)

    def test_overpaid_orders_report_lists_only_overpaid_orders(self):
        other = self.app.orders.create("bo", [("MUG", 1)])
        self.app.payments.handle_event(
            {"id": "evt_o", "type": "payment.succeeded", "order_id": other["id"], "amount_cents": 1200})
        self.pay("evt_1", 1200)
        self.pay("evt_2", 300)
        rows = reports.overpaid_orders(self.app.conn)
        self.assertEqual(rows, [{"order_id": self.order["id"], "customer": "ana", "total_cents": 1200,
                                 "paid_cents": 1500, "overpaid_cents": 300}])

    def test_overpaid_report_is_available_over_the_api(self):
        self.pay("evt_1", 1200)
        self.pay("evt_2", 1200)
        status, payload = self.app.handle("GET", "/reports/overpaid")
        self.assertEqual(status, 200)
        self.assertEqual([r["order_id"] for r in payload["orders"]], [self.order["id"]])


if __name__ == "__main__":
    unittest.main()
