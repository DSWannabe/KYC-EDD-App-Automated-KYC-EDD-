"""Kết nối SQLite. Mỗi request / job mở một kết nối riêng và tự đóng."""
import sqlite3
from pathlib import Path

from app import config

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def _mo(path):
    path = Path(path)
    # sqlite3 tự tạo file rỗng khi đường dẫn sai, nên kiểm tra trước để báo lỗi rõ
    if not path.is_file():
        raise FileNotFoundError(f"Không thấy file DB: {path}. Kiểm tra KYC_CORPUS_DB / KYC_COMPANY_DB.")
    con = sqlite3.connect(path, timeout=30)
    con.execute("pragma journal_mode=wal")   # đọc và ghi không chặn nhau
    con.row_factory = sqlite3.Row
    return con


def corpus():
    return _mo(config.CORPUS_DB)


def company():
    return _mo(config.COMPANY_DB)


def init_schema(con):
    """Tạo các bảng của app trong corpus.db nếu chưa có."""
    con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    # DB tạo trước khi có cột mới: thêm cột còn thiếu (create table if not exists không tự thêm)
    co = {r[1] for r in con.execute("pragma table_info(er_labels)")}
    for cot, kieu in [("score_lr", "real"), ("nguon", "text")]:
        if cot not in co:
            con.execute(f"alter table er_labels add column {cot} {kieu}")
    con.commit()
