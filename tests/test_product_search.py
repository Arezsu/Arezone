import sqlite3
import unittest

from modules.product_search import search_products


class ProductSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE products (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                brand TEXT,
                category TEXT,
                alt_codes TEXT DEFAULT ''
            )
            """
        )
        self.conn.executemany(
            "INSERT INTO products(code, name, brand, category, alt_codes) VALUES(?, ?, ?, ?, ?)",
            [
                ("P1", "Coca-Cola Zero 500ml", "Coca-Cola", "Bebidas", ""),
                ("P2", "Pepsi 500ml", "Pepsi", "Coca-Cola", ""),
                ("P3", "Agua mineral", "Aqua", "Bebidas", "CC-001"),
            ],
        )
        self.conn.commit()

    def test_search_does_not_match_category(self) -> None:
        rows = search_products(self.conn, "coca", limit=10)
        codes = [row["code"] for row in rows]
        self.assertEqual(codes, ["P1"])


if __name__ == "__main__":
    unittest.main()
