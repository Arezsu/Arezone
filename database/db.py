from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from modules.app_config import DATA_DIR


DB_PATH = DATA_DIR / "arezone.db"


def _migrate_legacy_paths() -> None:
    try:
        legacy_db = Path(__file__).resolve().parents[1] / "data" / "arezone.db"
        if legacy_db.exists() and not DB_PATH.exists():
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            DB_PATH.write_bytes(legacy_db.read_bytes())
    except Exception:
        pass


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    _migrate_legacy_paths()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            brand_code TEXT,
            brand TEXT,
            group_code TEXT,
            category TEXT,
            alt_codes TEXT DEFAULT '',
            stock REAL DEFAULT 0,
            has_tax INTEGER DEFAULT 0,
            tax_rate REAL DEFAULT 0,
            description TEXT,
            cost REAL DEFAULT 0,
            price_public REAL DEFAULT 0,
            price_1 REAL DEFAULT 0,
            price_2 REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            seller TEXT,
            customer TEXT,
            subtotal REAL NOT NULL,
            tax_total REAL NOT NULL,
            total REAL NOT NULL,
            cash REAL DEFAULT 0,
            nequi REAL DEFAULT 0,
            pse REAL DEFAULT 0,
            card REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            cheque REAL DEFAULT 0,
            other REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            payment_type TEXT,
            print_ticket INTEGER DEFAULT 1,
            status TEXT DEFAULT 'COMPLETED',
            voided_at TEXT,
            voided_reason TEXT,
            voided_by TEXT,
            refund_method TEXT
        );

        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            price_tier TEXT NOT NULL,
            cost REAL DEFAULT 0,
            tax_rate REAL DEFAULT 0,
            has_tax INTEGER DEFAULT 0,
            line_total REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS brand_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            brand TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS product_brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS product_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS held_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT 'VENTA EN ESPERA',
            payload TEXT NOT NULL
        );
        """
    )
    _add_missing_columns(conn, "products", {"stock": "REAL DEFAULT 0", "alt_codes": "TEXT DEFAULT ''"})
    _add_missing_columns(conn, "sales", {"nequi": "REAL DEFAULT 0", "pse": "REAL DEFAULT 0"})
    _add_missing_columns(
        conn,
        "sales",
        {
            "voided_at": "TEXT",
            "voided_reason": "TEXT",
            "voided_by": "TEXT",
            "refund_method": "TEXT",
        },
    )
    _add_missing_columns(conn, "held_sales", {"name": "TEXT NOT NULL DEFAULT 'VENTA EN ESPERA'"})
    conn.commit()


def ensure_runtime_settings(conn: sqlite3.Connection, invoice_prefix: str) -> None:
    _set_default(conn, "invoice_counter", "41999")
    _set_default(conn, "invoice_prefix", invoice_prefix)
    _set_default(conn, "theme", "day")
    _set_default(conn, "fullscreen", "0")
    _set_default(conn, "autostart", "0")
    _set_default(conn, "printer_port", "USB")
    _set_default(conn, "auto_print", "1")
    _set_default(conn, "auto_open_drawer", "1")
    _set_default(conn, "auto_night_enabled", "1")
    _set_default(conn, "night_start", "18:00")
    _set_default(conn, "night_end", "06:00")
    _set_default(conn, "sound_enabled", "1")
    conn.commit()


def _set_default(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
        (key, value),
    )


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def get_next_invoice_no(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = 'invoice_counter'").fetchone()
    current = int(row["value"]) if row else 41999
    prefix_row = conn.execute("SELECT value FROM settings WHERE key = 'invoice_prefix'").fetchone()
    prefix = prefix_row["value"] if prefix_row else "POS-"
    invoice = f"{prefix}{current}"
    conn.execute(
        """
        INSERT INTO settings(key, value)
        VALUES('invoice_counter', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(current + 1),),
    )
    conn.commit()
    return invoice


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def count_products(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS total FROM products").fetchone()
    return int(row["total"] if row else 0)
