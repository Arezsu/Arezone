from __future__ import annotations

import sqlite3
from typing import Sequence


def search_products(conn: sqlite3.Connection, query: str, limit: int = 500) -> list[sqlite3.Row]:
    """Search products by code, name, brand, and alternate codes.

    The search intentionally does not match against the category field so a text
    query such as 'Coca-Cola' will not return every product from that category.
    """

    text = (query or "").strip()
    pattern = f"%{text}%"
    if not text:
        return []

    return conn.execute(
        """
        SELECT * FROM products
        WHERE code LIKE ?
           OR name LIKE ?
           OR brand LIKE ?
           OR COALESCE(alt_codes, '') LIKE ?
        ORDER BY name
        LIMIT ?
        """,
        (pattern, pattern, pattern, pattern, limit),
    ).fetchall()
