import unittest

from tillpoint import db
from tillpoint.api import App


class CancelRestockTest(unittest.TestCase):
    """Report 2: stock is taken when the order is created, so cancelling an unpaid order must give it back."""

    def setUp(self):
        self.conn = db.connect()
        self.app = App(self.conn)
        self.app.catalog.add_product("TEE", "T-shirt", 2500, stock=5)

    def stock(self):
        return self.conn.execute("SELECT stock FROM products WHERE sku = 'TEE'").fetchone()["stock"]

    def test_cancelling_a_pending_order_restocks(self):
        order = self.app.orders.create("ana", [("TEE", 2)])
        self.assertEqual(self.stock(), 3)
        self.app.orders.cancel(order["id"])
        self.assertEqual(self.stock(), 5)

    def test_cancelling_twice_restocks_once(self):
        order = self.app.orders.create("ana", [("TEE", 2)])
        self.app.orders.cancel(order["id"])
        self.app.orders.cancel(order["id"])
        self.assertEqual(self.stock(), 5)


if __name__ == "__main__":
    unittest.main()
