"""
Kho bao cao thuong nien (SQLite). 3 bang:
  report_files : file goc anh tai ve (pdf/zip/rar), khoa chong trung = sha256
  report_docs  : moi PDF (1 file goc co the chua nhieu PDF), khoa chong trung = sha256
  report_pages : text tung trang cua PDF, de tim kiem (BM25...) sau nay
PDF goc luu tren dia (khong nhet vao DB); DB chi giu duong dan + text.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "reports.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS report_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    fiscal_year INTEGER,
    original_name TEXT NOT NULL,
    file_type TEXT NOT NULL,              -- pdf / zip / rar / 7z
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,                 -- ok / empty / needs_tool / error
    note TEXT,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES report_files(id),
    ticker TEXT NOT NULL,
    fiscal_year INTEGER,
    doc_type TEXT,                        -- annual_report / financial_statements / governance / sustainability / unknown
    relative_name TEXT NOT NULL,          -- ten PDF (ben trong archive neu co)
    stored_path TEXT NOT NULL,            -- duong dan tuong doi so voi thu muc luu tru
    sha256 TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL,
    page_count INTEGER,
    text_pages INTEGER,                   -- so trang co text
    text_chars INTEGER,
    status TEXT NOT NULL,                 -- ok / scanned_needs_ocr / garbled_text / error
    note TEXT
);
CREATE INDEX IF NOT EXISTS report_docs_ticker_idx ON report_docs (ticker, fiscal_year);

CREATE TABLE IF NOT EXISTS report_pages (
    doc_id INTEGER NOT NULL REFERENCES report_docs(id),
    page_no INTEGER NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (doc_id, page_no)
);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def connect(path=None) -> sqlite3.Connection:
    path = Path(path) if path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def find_file(conn, sha256: str):
    return conn.execute("SELECT id, status, ticker, original_name FROM report_files WHERE sha256 = ?", (sha256,)).fetchone()


def delete_file(conn, file_id: int):
    """Xoa 1 file goc va moi thu lien quan (de nap lai khi truoc do bi loi)."""
    doc_ids = [r[0] for r in conn.execute("SELECT id FROM report_docs WHERE file_id = ?", (file_id,))]
    for d in doc_ids:
        conn.execute("DELETE FROM report_pages WHERE doc_id = ?", (d,))
    conn.execute("DELETE FROM report_docs WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM report_files WHERE id = ?", (file_id,))


def insert_file(conn, **f) -> int:
    cur = conn.execute(
        """INSERT INTO report_files (ticker, fiscal_year, original_name, file_type, size_bytes,
                                     sha256, status, note, ingested_at)
           VALUES (:ticker, :fiscal_year, :original_name, :file_type, :size_bytes,
                   :sha256, :status, :note, :ingested_at)""",
        {**f, "ingested_at": _now()},
    )
    return cur.lastrowid


def doc_id_by_sha(conn, sha256: str):
    row = conn.execute("SELECT id FROM report_docs WHERE sha256 = ?", (sha256,)).fetchone()
    return row[0] if row else None


def insert_doc(conn, **d) -> int:
    cur = conn.execute(
        """INSERT INTO report_docs (file_id, ticker, fiscal_year, doc_type, relative_name, stored_path,
                                    sha256, size_bytes, page_count, text_pages, text_chars, status, note)
           VALUES (:file_id, :ticker, :fiscal_year, :doc_type, :relative_name, :stored_path,
                   :sha256, :size_bytes, :page_count, :text_pages, :text_chars, :status, :note)""", d)
    return cur.lastrowid


def insert_pages(conn, doc_id: int, pages: list[tuple[int, str]]):
    conn.executemany("INSERT INTO report_pages (doc_id, page_no, text) VALUES (?, ?, ?)",
                     [(doc_id, no, text) for no, text in pages])