"""
Bo sung chi tiet (ten quoc te, ngay hoat dong, tinh trang, loai hinh, dien thoai, nganh nghe)
cho cac dong trong companies.db chua co. Dong cu va dong moi deu duoc xu ly:
chi can detail_fetched_at con trong.
Chay tu thu muc kyc_crawler:  python -m core.enrich_details --limit 5
"""

import argparse
import time
from datetime import datetime, timezone

import requests

from core.orchestrator_all import fetch_with_retry
from core.storage import get_connection, init_db
from parsers.masothue_detail import LABELS, parse_detail

COLUMNS = list(LABELS.values())


def rows_to_enrich(limit, only_query):
    conn = get_connection()
    sql = "SELECT id, detail_url, company_name FROM companies WHERE detail_fetched_at IS NULL AND detail_url IS NOT NULL"
    params = []
    if only_query:
        sql += " AND query = ?"
        params.append(only_query)
    sql += " ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def save_detail(row_id, detail):
    sets = ", ".join(f"{c} = ?" for c in COLUMNS) + ", detail_fetched_at = ?"
    values = [detail[c] for c in COLUMNS] + [datetime.now(timezone.utc).isoformat(), row_id]
    conn = get_connection()
    conn.execute(f"UPDATE companies SET {sets} WHERE id = ?", values)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="chi chay N dong dau, de thu")
    ap.add_argument("--query", help="chi bo sung cho cac dong thuoc truy van nay")
    ap.add_argument("--delay", type=float, default=6)
    ap.add_argument("--max-errors", type=int, default=3)
    ap.add_argument("--cooldown", type=int, default=180)
    ap.add_argument("--max-waits", type=int, default=3)
    args = ap.parse_args()

    init_db()
    rows = rows_to_enrich(args.limit, args.query)
    print(f"Can bo sung {len(rows)} dong")

    errors_in_row = 0
    done = 0
    for row_id, url, name in rows:
        try:
            html = fetch_with_retry(url, "masothue", 2, args)
        except requests.RequestException as e:
            code = getattr(e.response, "status_code", None)
            errors_in_row += 1
            print(f"  [loi] {name}: {code or type(e).__name__}")
            if code in (403, 429) or errors_in_row >= args.max_errors:
                print("DUNG: bi chan hoac loi lien tiep. Doi lau roi chay lai (tien do da luu).")
                break
            continue

        errors_in_row = 0
        save_detail(row_id, parse_detail(html))
        done += 1
        print(f"  [{done}/{len(rows)}] {name}")
        time.sleep(args.delay)

    print(f"Xong. Da bo sung {done} dong.")
