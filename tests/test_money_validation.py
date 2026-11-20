import unittest

from tillpoint import db
from tillpoint.api import App


class MoneyValidationTest(unittest.TestCase):
    """Amounts coming in from outside must be non-negative whole cents; anything else is a 400."""

    def setUp(self):
        self.app = App(db.connect())
        self.app.catalog.add_product("MUG", "Mug", 1200, stock=10)
        self.order = self.app.orders.create("ana", [("MUG", 1)])

    def webhook(self, amount, event_id="evt_x"):
        return self.app.handle("POST", "/webhooks/payments", {
            "id": event_id, "type": "payment.succeeded", "order_id": self.order["id"], "amount_cents": amount})

    def test_negative_payment_is_rejected_and_not_recorded(self):
        status, _ = self.webhook(-1200)
        self.assertEqual(status, 400)
        self.assertEqual(self.app.payments.paid_cents(self.order["id"]), 0)

    def test_non_integer_payment_is_rejected(self):
        for bad in (12.5, "1200", None, True):
            status, _ = self.webhook(bad, event_id=f"evt_{bad!r}")
            self.assertEqual(status, 400, bad)

    def test_fractional_price_is_rejected(self):
        status, _ = self.app.handle("PUT", "/products/MUG", {"price_cents": 99.5})
        self.assertEqual(status, 400)
        self.assertEqual(self.app.catalog.get_product("MUG").price_cents, 1200)


if __name__ == "__main__":
    unittest.main()
