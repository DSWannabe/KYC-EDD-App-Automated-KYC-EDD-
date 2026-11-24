"""Tạo DB mẫu nhỏ từ corpus.db và companies.db thật.

Cách dùng:
    python scripts/make_sample_db.py --source-dir /duong/dan/thu_muc_chua_2_file_db

Chọn N bài: trước hết các bài nhắc những tên trong TU_KHOA (có cả ca khó như ACBS, FPT Shop),
rồi bổ sung ngẫu nhiên cho đủ N. Kết quả ghi vào data/sample/ (corpus.db, companies.db).
"""
import argparse
import random
import shutil
import sqlite3
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]

# Mỗi từ khóa lấy tối đa MOI_TU_KHOA bài
TU_KHOA = ["Petrolimex", "Vingroup", "ACBS", "FPT Shop", "VNDIRECT", "Hòa Phát", "Vinhomes", "Sacombank"]
MOI_TU_KHOA = 8


def chon_bai(con, n, seed):
    ids = []
    for tu in TU_KHOA:
        dong = con.execute(
            "select id from articles where title like ? or cleaned_text like ? order by id limit ?",
            (f"%{tu}%", f"%{tu}%", MOI_TU_KHOA)).fetchall()
        ids += [r[0] for r in dong]
    ids = list(dict.fromkeys(ids))[:n]   # bỏ trùng, giữ thứ tự

    da_chon = set(ids)
    con_lai = [r[0] for r in con.execute("select id from articles") if r[0] not in da_chon]
    random.Random(seed).shuffle(con_lai)
    return ids + con_lai[:max(0, n - len(ids))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", required=True, help="thư mục chứa corpus.db và companies.db")
    ap.add_argument("--out", default=str(PROJECT / "data" / "sample"))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    nguon = Path(a.source_dir)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in ["corpus.db", "companies.db"]:
        if not (nguon / f).is_file():
            raise FileNotFoundError(nguon / f)

    shutil.copy2(nguon / "companies.db", out / "companies.db")

    src = sqlite3.connect(nguon / "corpus.db")
    ids = chon_bai(src, a.n, a.seed)
    sql_tao_bang = src.execute("select sql from sqlite_master where type='table' and name='articles'").fetchone()[0]

    dich = out / "corpus.db"
    if dich.exists():
        dich.unlink()
    dst = sqlite3.connect(dich)
    dst.execute(sql_tao_bang)
    dau_hoi = ",".join("?" * len(ids))
    dong = src.execute(f"select * from articles where id in ({dau_hoi})", ids).fetchall()
    dst.executemany(f"insert into articles values ({','.join('?' * len(dong[0]))})", dong)
    dst.commit()
    print("Đã ghi", len(dong), "bài vào", dich)


if __name__ == "__main__":
    main()
