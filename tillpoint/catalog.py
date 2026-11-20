"""Product catalog. SQLite is the only source of truth: with several workers a per-process cache goes stale."""
from dataclasses import dataclass


class OutOfStock(Exception):
    def __init__(self, sku, wanted, available):
        super().__init__(f"{sku}: wanted {wanted}, {available} available")
        self.sku, self.wanted, self.available = sku, wanted, available


class UnknownProduct(Exception):
    pass


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price_cents: int
    stock: int


class Catalog:
    def __init__(self, conn):
        self.conn = conn

    def add_product(self, sku, name, price_cents, stock=0):
        self.conn.execute(
            "INSERT INTO products (sku, name, price_cents, stock) VALUES (?, ?, ?, ?)",
            (sku, name, price_cents, stock),
        )

    def get_product(self, sku):
        row = self.conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
        if row is None:
            raise UnknownProduct(sku)
        return Product(row["sku"], row["name"], row["price_cents"], row["stock"])

    def update_price(self, sku, price_cents):
        if type(price_cents) is not int or price_cents < 0:
            raise ValueError("price_cents must be a non-negative whole number of cents")
        cur = self.conn.execute("UPDATE products SET price_cents = ? WHERE sku = ?", (price_cents, sku))
        if cur.rowcount == 0:
            raise UnknownProduct(sku)

    def reserve(self, sku, qty):
        """Take qty units out of stock, or raise OutOfStock."""
        # One atomic statement: the check and the decrement can't be separated by another worker.
        cur = self.conn.execute(
            "UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?", (qty, sku, qty))
        if cur.rowcount == 0:
            raise OutOfStock(sku, qty, self.get_product(sku).stock)  # UnknownProduct if the sku doesn't exist

    def release(self, sku, qty):
        """Put qty units back into stock."""
        self.conn.execute("UPDATE products SET stock = stock + ? WHERE sku = ?", (qty, sku))
