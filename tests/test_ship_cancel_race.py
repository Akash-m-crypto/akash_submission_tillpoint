import unittest

from tillpoint import db
from tillpoint.api import App
from tillpoint.orders import OrderError


class ShipCancelRaceTest(unittest.TestCase):
    """If a cancel lands between ship() reading the order and writing 'shipped', the order must stay cancelled."""

    def setUp(self):
        self.app = App(db.connect())
        self.app.catalog.add_product("MUG", "Mug", 1200, stock=5)
        self.order = self.app.orders.create("ana", [("MUG", 1)])
        self.app.payments.handle_event(
            {"id": "evt_1", "type": "payment.succeeded", "order_id": self.order["id"], "amount_cents": 1200})

    def test_cancelled_order_is_not_overwritten_by_a_stale_ship(self):
        orders = self.app.orders
        real_get, state = orders.get, {"raced": False}

        def get_then_cancel(order_id):
            result = real_get(order_id)           # ship sees 'paid'...
            if not state["raced"]:
                state["raced"] = True
                orders.cancel(order_id)           # ...then another worker cancels before ship writes
            return result

        orders.get = get_then_cancel
        with self.assertRaises(OrderError):
            orders.ship(self.order["id"])
        orders.get = real_get
        self.assertEqual(orders.get(self.order["id"])["status"], "cancelled")
        self.assertEqual(self.app.catalog.get_product("MUG").stock, 5)


if __name__ == "__main__":
    unittest.main()
