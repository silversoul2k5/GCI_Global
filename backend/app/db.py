"""
Thin SQLite access layer.

Two tables live in the same file (backend/data/customers.db):
- `customers`   : written once by ml/train.py (one row per customer, with a
                  precomputed churn risk_score/risk_band).
- `offers`      : written at runtime by this API when the company sends an
                  offer, and updated when the customer's app redeems it.
                  This is the shared state the website and the Expo app
                  both read/write, which is what makes "send an offer on the
                  website -> it shows up on the customer's phone" work: both
                  sides are just clients of the same backend + database.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "customers.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_offers_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            offer_type TEXT NOT NULL,
            message TEXT NOT NULL,
            discount_value TEXT,
            status TEXT NOT NULL DEFAULT 'sent',
            created_at TEXT NOT NULL,
            redeemed_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def customers_table_exists():
    conn = get_conn()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='customers'"
    ).fetchone()
    conn.close()
    return row is not None
