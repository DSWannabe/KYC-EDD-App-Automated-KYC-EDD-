"""Chuẩn hóa companies.db. Chạy một lần; chạy lại không sao.

Tạo (từ app/db/schema_companies.sql):
- company_profiles: hồ sơ đã chọn lọc, khóa ticker, lấy từ bảng snapshot VN100
- index_members: thành viên rổ VN100 theo ngày
- view vn100: cùng cột với bảng snapshot cũ, luôn lấy rổ mới nhất
- lookup_queries, lookup_candidates: log tra cứu (chỉ tạo bảng rỗng)

Không xóa bảng nào. Sao lưu file trước khi sửa.

Chạy trong thư mục backend/:
    python scripts/migrate_companies_db.py                       # DB theo config (mặc định data/sample)
    python scripts/migrate_companies_db.py --db /duong/dan/companies.db
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config

SCHEMA = config.BACKEND / "app" / "db" / "schema_companies.sql"
COT = ["ticker", "tax_id", "company_name", "key_leaders", "address", "industry", "industry_keywords", "website"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(config.COMPANY_DB))
    ap.add_argument("--snapshot", default="vn100_20261106", help="bảng danh mục VN100 cũ")
    ap.add_argument("--ngay", default="2026-11-06", help="ngày hiệu lực của rổ trong snapshot")
    a = ap.parse_args()

    db = Path(a.db)
    if not db.is_file():
        raise FileNotFoundError(db)

    # 1. Sao lưu
    bay_gio = datetime.now(timezone.utc)
    sao_luu = db.with_name(f"{db.stem}_truoc_chuan_hoa_{bay_gio:%Y%m%d_%H%M%S}.db")
    shutil.copy2(db, sao_luu)
    print("đã sao lưu:", sao_luu)

    con = sqlite3.connect(db)

    # 2. Tạo bảng và view
    con.executescript(SCHEMA.read_text(encoding="utf-8"))

    # 3. Chép hồ sơ và thành viên rổ từ snapshot
    cot = ", ".join(COT)
    con.execute(f'insert or replace into company_profiles ({cot}, updated_at) '
                f'select {cot}, ? from "{a.snapshot}"', (bay_gio.isoformat(),))
    con.execute(f'insert or ignore into index_members select ?, ticker, ? from "{a.snapshot}"', ("VN100", a.ngay))
    con.commit()

    # 4. Kiểm tra: view vn100 phải trả đúng các dòng như snapshot (trừ short_name, lấy từ company_names)
    cu = set(con.execute(f'select {cot} from "{a.snapshot}"'))
    moi = set(con.execute(f"select {cot} from vn100"))
    print("snapshot:", len(cu), "dòng | view vn100:", len(moi), "dòng | khớp:", cu == moi)

    lech = con.execute(f'''select s.ticker, s.short_name, n.short_name from "{a.snapshot}" s
                           left join company_names n on n.ticker = s.ticker
                           where coalesce(s.short_name, '') != coalesce(n.short_name, '')''').fetchall()
    if lech:
        print(f"short_name khác nhau giữa snapshot và company_names ({len(lech)} mã), view dùng company_names:")
        for r in lech[:10]:
            print("  ", r)
    con.close()

    if cu != moi:
        raise SystemExit("View không khớp snapshot. Khôi phục từ bản sao lưu và báo lại.")
    print("Xong. Đổi CATALOG = \"vn100\" trong app/config.py.")


if __name__ == "__main__":
    main()
