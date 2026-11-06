"""A small starting test suite for the order desk."""

from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService


class OrderSmokeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def test_regular_pickup_quote(self):
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 2}])
        self.assertEqual(quote["subtotal_cents"], 1000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 1000)

    def test_student_delivery_quote(self):
        quote = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}], "delivery")
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 600)
        self.assertEqual(quote["total_cents"], 7800)

    def test_order_can_be_reopened(self):
        order = self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.assertEqual(order["order_id"], "ORD-0001")
        self.assertEqual(order["status"], "placed")
        self.assertEqual(OrderService(self.path).get_order(order["order_id"]), order)

    def test_cancel_order_restores_stock(self):
        before = self.service.catalog()
        order = self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 2}])
        cancelled = self.service.cancel_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(self.service.catalog(), before)

    def test_remove_stock_on_successful_order(self):
        before = self.service.catalog()
        order = self.service.place_order("regular", [{"product_id": "notebook", "quantity": 4}])
        after = self.service.catalog()
        self.assertEqual(after[0]["stock"], before[0]["stock"] - 4)

    def test_student_gets_discount_at_threshold_exactly(self):
        order = self.service.place_order("student", [{"product_id": "notebook", "quantity": 4}, {"product_id": "mug", "quantity": 2}])
        self.assertEqual(order["subtotal_cents"], 5000)
        self.assertEqual(order["discount_cents"], 500)

    def test_customer_type_is_not_accepted_if_invalid(self):
        with self.assertRaises(ValueError):
            self.service.quote("NotRegularOrStudent", [{"product_id": "pen-pack", "quantity": 3}])

    def test_quotes_do_not_change_stock(self):
        before = self.service.catalog()
        self.service.quote("regular", [{"product_id": "bag", "quantity": 2}])
        after = self.service.catalog()
        self.assertEqual(before, after)

    def test_express_for_regular_customer_quote(self):
        quote = self.service.quote("regular", [{"product_id": "hoodie", "quantity": 1}], "express")
        self.assertEqual(quote["subtotal_cents"], 4000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 5200)

    def test_express_for_student_customer_quote(self):
        quote = self.service.quote("student", [{"product_id": "bag", "quantity": 2}], "express")
        self.assertEqual(quote["subtotal_cents"], 5000)
        self.assertEqual(quote["discount_cents"], 500)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 5700)

    def test_express_fee_is_not_waived(self):
        order = self.service.place_order("regular", [{"product_id": "hoodie", "quantity": 2}, {"product_id": "mug", "quantity": 2}], "express")
        self.assertEqual(order["subtotal_cents"], 11000)
        self.assertEqual(order["delivery_cents"], 1200)
        self.assertEqual(order["total_cents"], 12200)

    def test_express_order_cancellations_preserves_data(self):
        order = self.service.place_order("student", [{"product_id": "bag", "quantity": 3}], "express")
        cancelled_order = self.service.cancel_order(order["order_id"])
        self.assertEqual(cancelled_order["status"], "cancelled")
        self.assertEqual(cancelled_order["fulfillment"], "express")
        self.assertEqual(cancelled_order["delivery_cents"], 1200)
        self.assertEqual(cancelled_order["discount_cents"], 750)
        self.assertEqual(cancelled_order["total_cents"], 7950)


if __name__ == "__main__":
    unittest.main()
