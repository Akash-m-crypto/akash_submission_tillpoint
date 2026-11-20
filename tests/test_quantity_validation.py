import unittest

from tillpoint import db
from tillpoint.api import App
from tillpoint.orders import OrderError


class QuantityValidationTest(unittest.TestCase):
    """Quantities are whole units: 1.5 or True must not be able to leave fractional stock behind."""

    def setUp(self):
        self.app = App(db.connect())
        self.app.catalog.add_product("MUG", "Mug", 1200, stock=10)

    def stock(self):
        return self.app.catalog.get_product("MUG").stock

    def test_non_integer_quantities_are_rejected_and_stock_untouched(self):
        for bad in (1.5, 0.5, True, "2", None):
            with self.assertRaises((OrderError, TypeError), msg=repr(bad)):
                self.app.orders.create("ana", [("MUG", bad)])
            self.assertEqual(self.stock(), 10, repr(bad))

    def test_whole_quantity_still_works(self):
        self.app.orders.create("ana", [("MUG", 3)])
        self.assertEqual(self.stock(), 7)


if __name__ == "__main__":
    unittest.main()
