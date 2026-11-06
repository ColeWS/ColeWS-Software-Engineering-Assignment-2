"""Operations used by the command-line order desk."""

from supplydesk.storage import JsonStore


class OrderService:
    MIN_QUANTITY = 1
    MAX_QUANTITY = 99
    STUDENT_DISCOUNT_THRESHOLD = 5000
    STUDENT_DISCOUNT_PERCENT = 10
    ROUNDING_ADJUSTMENT = 50
    DELIVERY_DISCOUNT_THRESHOLD = 10000
    DELIVERY_COST = 600

    def __init__(self, state_path=".supplydesk/state.json"):
        self.store = JsonStore(state_path)

    def catalog(self):
        return self.store.load()["catalog"]

    def validate_request(self, state, customer_type, items, fulfillment):
        if customer_type not in ("regular", "student"):
            raise ValueError("Customer type must be regular or student.")
        if fulfillment not in ("pickup", "delivery"):
            raise ValueError("Fulfillment must be pickup or delivery.")
        if not isinstance(items, list) or not items:
            raise ValueError("An order must contain at least one item.")
        lines = []
        subtotal = 0
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each item must contain a product_id and quantity.")
            product = None
            for candidate in state["catalog"]:
                if candidate["product_id"] == item.get("product_id"):
                    product = candidate
                    break
            if product is None:
                raise ValueError("Unknown product.")
            quantity = item.get("quantity")
            if type(quantity) is not int or quantity < self.MIN_QUANTITY or quantity > self.MAX_QUANTITY:
                raise ValueError("Quantity must be an integer from 1 to 99.")
            if quantity > product["stock"]:
                raise ValueError("Not enough stock for " + product["product_id"] + ".")
            line_total = product["unit_price_cents"] * quantity
            subtotal += line_total
            lines.append({
                "product_id": product["product_id"],
                "name": product["name"],
                "unit_price_cents": product["unit_price_cents"],
                "quantity": quantity,
                "line_total_cents": line_total,
            })
        return lines, subtotal
        
    def calculate_total(self, subtotal, customer_type, fulfillment):
        discount = 0
        if customer_type == "student" and subtotal >= self.STUDENT_DISCOUNT_THRESHOLD:
            discount = (subtotal * self.STUDENT_DISCOUNT_PERCENT + self.ROUNDING_ADJUSTMENT) // 100
        delivery = 0
        if fulfillment == "delivery" and subtotal - discount < self.DELIVERY_DISCOUNT_THRESHOLD:
            delivery = self.DELIVERY_COST
        return discount, delivery

    def create_order(self, state, customer_type, fulfillment, lines, subtotal, discount, delivery):
        order = {
            "order_id": "ORD-" + str(state["next_order_number"]).zfill(4),
            "status": "placed",
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }
        return order

    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        lines, subtotal = self.validate_request(state, customer_type, items, fulfillment)
        discount, delivery = self.calculate_total(subtotal, customer_type, fulfillment)
        return {
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }

    def place_order(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        lines, subtotal = self.validate_request(state, customer_type, items, fulfillment)
        discount, delivery = self.calculate_total(subtotal, customer_type, fulfillment)
        order = self.create_order(state, customer_type, fulfillment, lines, subtotal, discount, delivery)
        for line in lines:
            for product in state["catalog"]:
                if product["product_id"] == line["product_id"]:
                    product["stock"] -= line["quantity"]
        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)
        return order

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        state = self.store.load()
        for order in state["orders"]:
            if order["order_id"] == order_id:
                return order
        raise ValueError("Unknown order: " + order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = None
        for candidate in state["orders"]:
            if candidate["order_id"] == order_id:
                order = candidate
                break
        if order is None:
            raise ValueError("Unknown order: " + order_id)
        for line in order["items"]:
            for product in state["catalog"]:
                if product["product_id"] == line["product_id"]:
                    product["stock"] += line["quantity"]
        order["status"] = "cancelled"
        self.store.save(state)
        return order
