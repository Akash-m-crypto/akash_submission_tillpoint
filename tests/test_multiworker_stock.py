import os
import tempfile
import unittest

from tillpoint import db
from tillpoint.api import App
from tillpoint.catalog import OutOfStock


class MultiWorkerStockTest(unittest.TestCase):
    """Report 5: two workers = two processes = two App objects over one database file, each with its own cache."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.a = App(db.connect(self.path))
        self.b = App(db.connect(self.path))
        self.a.catalog.add_product("TEE", "T-shirt", 2500, stock=1)

    def tearDown(self):
        os.remove(self.path)

    def test_second_worker_cannot_sell_the_last_unit_again(self):
        self.a.catalog.get_product("TEE")   # worker A has seen stock=1 and cached it
        self.b.orders.create("bo", [("TEE", 1)])
        with self.assertRaises(OutOfStock):
            self.a.orders.create("ana", [("TEE", 1)])
        stock = self.a.conn.execute("SELECT stock FROM products WHERE sku = 'TEE'").fetchone()["stock"]
        self.assertEqual(stock, 0)

    def test_price_change_on_one_worker_is_seen_by_the_other(self):
        self.b.catalog.get_product("TEE")
        self.a.handle("PUT", "/products/TEE", {"price_cents": 3000})
        order = self.b.orders.create("bo", [("TEE", 1)])
        self.assertEqual(order["subtotal_cents"], 3000)

    def test_two_workers_cancelling_the_same_order_restock_once(self):
        self.a.catalog.add_product("MUG", "Mug", 1200, stock=5)
        order = self.a.orders.create("ana", [("MUG", 2)])
        a_cancel = lambda: self.a.orders.cancel(order["id"])

        class RacingConn:
            """Worker B's connection: worker A's cancel lands just before B takes its write lock."""
            def __init__(self, conn):
                self._conn, self._raced = conn, False

            def execute(self, sql, *args):
                if sql == "BEGIN IMMEDIATE" and not self._raced:
                    self._raced = True
                    a_cancel()
                return self._conn.execute(sql, *args)

            def __getattr__(self, name):
                return getattr(self._conn, name)

        self.b.orders.conn = RacingConn(self.b.conn)
        self.b.orders.cancel(order["id"])
        stock = self.a.conn.execute("SELECT stock FROM products WHERE sku = 'MUG'").fetchone()["stock"]
        self.assertEqual(stock, 5)


if __name__ == "__main__":
    unittest.main()
