import unittest

from tillpoint import db
from tillpoint.api import App


class TaxWithCouponTest(unittest.TestCase):
    """Report 3: sales tax is charged on what the customer pays for the goods, i.e. after the discount."""

    def setUp(self):
        self.conn = db.connect()
        self.app = App(self.conn)
        self.app.catalog.add_product("TEE", "T-shirt", 10000, stock=5)
        self.conn.execute("INSERT INTO coupons (code, kind, value) VALUES ('TEN', 'percent', 10)")
        self.conn.execute("INSERT INTO coupons (code, kind, value) VALUES ('FIVER', 'fixed', 500)")

    def test_percent_coupon_reduces_taxable_amount(self):
        order = self.app.orders.create("ana", [("TEE", 1)], region="CA", coupon_code="TEN")
        # 10000 - 1000 = 9000 taxable; 7.25% of 9000 = 652.5 -> 653
        self.assertEqual(order["discount_cents"], 1000)
        self.assertEqual(order["tax_cents"], 653)
        self.assertEqual(order["total_cents"], 9653)

    def test_fixed_coupon_reduces_taxable_amount(self):
        order = self.app.orders.create("ana", [("TEE", 1)], region="TX", coupon_code="FIVER")
        # 10000 - 500 = 9500 taxable; 6.25% of 9500 = 593.75 -> 594
        self.assertEqual(order["tax_cents"], 594)
        self.assertEqual(order["total_cents"], 10094)

    def test_no_coupon_unchanged(self):
        order = self.app.orders.create("ana", [("TEE", 1)], region="CA")
        self.assertEqual(order["tax_cents"], 725)


if __name__ == "__main__":
    unittest.main()
