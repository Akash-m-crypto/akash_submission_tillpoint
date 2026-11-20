import unittest

from tillpoint import db
from tillpoint.api import App


class FreeOrderTest(unittest.TestCase):
    """An order whose total is 0 (100% coupon) will never get a payment, so it must not wait for one."""

    def setUp(self):
        self.app = App(db.connect())
        self.app.catalog.add_product("MUG", "Mug", 1200, stock=10)
        self.app.conn.execute("INSERT INTO coupons (code, kind, value) VALUES ('FREE', 'percent', 100)")

    def test_zero_total_order_is_paid_immediately_and_can_ship(self):
        order = self.app.orders.create("ana", [("MUG", 1)], coupon_code="FREE")
        self.assertEqual(order["total_cents"], 0)
        self.assertEqual(order["status"], "paid")
        self.assertEqual(self.app.orders.ship(order["id"])["status"], "shipped")

    def test_normal_order_still_starts_pending(self):
        self.assertEqual(self.app.orders.create("ana", [("MUG", 1)])["status"], "pending")


if __name__ == "__main__":
    unittest.main()
