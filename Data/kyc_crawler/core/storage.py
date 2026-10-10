"""
Luu Tier 1 vao SQLite. Bo qua ban ghi trung theo (source, tax_code).
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent.parent / "data" / "companies.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    company_name TEXT,
    tax_code TEXT,
    legal_rep TEXT,
    address TEXT,
    detail_url TEXT,
    retrieved_at TEXT NOT NULL
);

-- Trung = cung source + tax_code. Record thieu tax_code van duoc luu binh thuong.
CREATE UNIQUE INDEX IF NOT EXISTS companies_source_taxcode_idx
    ON companies (source, tax_code)
    WHERE tax_code IS NOT NULL;
"""


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH, timeout=30)  # cho toi 30s neu file dang bi khoa


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def insert_records(source: str, query: str, records: list[dict]):
    """Them record moi, tu bo qua record da co (cung source + tax_code)."""
    init_db()
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()

    for r in records:
        conn.execute(
            """INSERT INTO companies
               (source, query, company_name, tax_code, legal_rep, address, detail_url, retrieved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (source, tax_code) WHERE tax_code IS NOT NULL DO NOTHING""",
            (source, query, r.get("company_name"), r.get("tax_code"),
             r.get("legal_rep"), r.get("address"), r.get("detail_url"), now),
        )

    conn.commit()
    conn.close()