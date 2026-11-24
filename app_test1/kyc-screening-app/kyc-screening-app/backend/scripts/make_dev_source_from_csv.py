"""Chỉ dùng khi KHÔNG có corpus.db / companies.db thật (ví dụ môi trường kiểm tra).

Dựng một cặp DB "nguồn" có cùng tên bảng và cột với DB thật, từ các file CSV của benchmark:
- articles: từ kyc_v3/ket_qua/bai_sach.csv (chỉ các bài có trong cap_danh_gia.csv)
- company_names: từ seed/vn100_aliases.csv
- vn100_20261106: từ seed/vn100_20261106.csv

Sau đó chạy make_sample_db.py trên cặp DB này để lấy 100 bài.

Cách dùng:
    python scripts/make_dev_source_from_csv.py --kyc-v3 /duong/dan/kyc_v3 --out /tmp/nguon
"""
import argparse
import sqlite3
from pathlib import Path

import pandas as pd

SEED = Path(__file__).resolve().parent / "seed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kyc-v3", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    kq = Path(a.kyc_v3) / "ket_qua"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    cap = pd.read_csv(kq / "cap_danh_gia.csv")
    bai = pd.read_csv(kq / "bai_sach.csv", keep_default_na=False)
    bai = bai[bai["id"].isin(cap["article_id"])]

    # cleaned_text của DB thật có dòng tiêu đề lặp ở đầu, nên ghép lại cho giống
    articles = pd.DataFrame({
        "id": bai["id"], "title": bai["title"],
        "cleaned_text": bai["title"] + "\n" + bai["noi_dung"],
        "published_at": bai["published_at"], "source": bai["source"], "source_url": bai["source_url"],
    })

    corpus = out / "corpus.db"
    if corpus.exists():
        corpus.unlink()
    con = sqlite3.connect(corpus)
    con.execute("create table articles (id integer primary key, title text, cleaned_text text, "
                "published_at text, source text, source_url text)")
    articles.to_sql("articles", con, if_exists="append", index=False)
    con.commit()
    con.close()

    companies = out / "companies.db"
    if companies.exists():
        companies.unlink()
    con = sqlite3.connect(companies)
    pd.read_csv(SEED / "vn100_aliases.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False) \
        .to_sql("company_names", con, index=False)
    pd.read_csv(SEED / "vn100_20261106.csv", dtype=str, keep_default_na=False) \
        .to_sql("vn100_20261106", con, index=False)   # dtype=str để MST không mất số 0 đầu
    con.commit()
    con.close()
    print("Đã ghi", len(articles), "bài và 2 bảng công ty vào", out)


if __name__ == "__main__":
    main()
