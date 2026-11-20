import unittest
from datetime import datetime, timezone

from tillpoint import db, reports
from tillpoint.api import App


class ReportTimezoneTest(unittest.TestCase):
    """Report 4: a shop-local day in UTC+5:30 runs from 18:30Z the evening before to 18:30Z."""

    IST = 330

    def setUp(self):
        self.conn = db.connect()
        self.app = App(self.conn)
        self.app.catalog.add_product("MUG", "Mug", 1200, stock=10)

    def pay(self, event_id, when):
        order = self.app.orders.create("ana", [("MUG", 1)])
        self.app.payments.handle_event(
            {"id": event_id, "type": "payment.succeeded", "order_id": order["id"], "amount_cents": 1200}, now=when)

    def test_day_bounds_east_of_utc(self):
        self.assertEqual(reports.day_bounds_utc("2025-03-10", self.IST),
                         ("2025-03-09T18:30:00Z", "2025-03-10T18:30:00Z"))

    def test_day_bounds_west_of_utc(self):
        self.assertEqual(reports.day_bounds_utc("2025-03-10", -300),
                         ("2025-03-10T05:00:00Z", "2025-03-11T05:00:00Z"))

    def test_morning_sale_in_india_lands_on_its_own_day(self):
        # 08:00 IST on 10 March = 02:30Z on 10 March
        self.pay("evt_m", datetime(2025, 3, 10, 2, 30, tzinfo=timezone.utc))
        on_day = reports.daily_sales(self.conn, "2025-03-10", self.IST)
        day_before = reports.daily_sales(self.conn, "2025-03-09", self.IST)
        self.assertEqual(on_day["revenue_cents"], 1200)
        self.assertEqual(day_before["revenue_cents"], 0)

    def test_late_evening_sale_in_india_belongs_to_that_local_day(self):
        # 23:00 IST on 10 March = 17:30Z on 10 March
        self.pay("evt_e", datetime(2025, 3, 10, 17, 30, tzinfo=timezone.utc))
        self.assertEqual(reports.daily_sales(self.conn, "2025-03-10", self.IST)["revenue_cents"], 1200)
        self.assertEqual(reports.daily_sales(self.conn, "2025-03-11", self.IST)["revenue_cents"], 0)


if __name__ == "__main__":
    unittest.main()
