"""Nhận tên, mã chứng khoán hoặc mã số thuế của một công ty, trả về báo cáo sàng lọc.

    python run_screen.py "Hòa Phát"
    python run_screen.py 0900189284
    python run_screen.py HPG --date-from 2021-01-01

Cần chạy run_background.py trước để các bài đã được gắn nhãn ER và có vector.
"""
import argparse
import sys

import config
import db
import llm_read
import report
import retrieval
from resolve import company_row, profile, resolve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="tên công ty, mã chứng khoán hoặc mã số thuế")
    ap.add_argument("--date-from", default=None, help="chỉ lấy bài từ ngày này, dạng YYYY-MM-DD")
    args = ap.parse_args()

    con_c = db.companies()
    matches = resolve(args.query, con_c)
    if not matches:
        print(f"Không tìm thấy '{args.query}' trong danh mục {config.CATALOG_TABLE}.")
        print("Hệ thống hiện chỉ hỗ trợ các công ty trong danh mục này.")
        sys.exit(1)
    if len(matches) > 1:
        print(f"'{args.query}' khớp với nhiều công ty, hãy nhập mã chứng khoán hoặc mã số thuế:")
        for t, name, how in matches:
            print(f"  {t}  {name}  (khớp theo {how})")
        sys.exit(2)

    ticker, name, how = matches[0]
    print(f"Công ty: {ticker} - {name} (khớp theo {how})")
    row = company_row(con_c, ticker)
    prof = profile(con_c, ticker)

    con = db.corpus()
    if con.execute("select count(*) from er_scan").fetchone()[0] == 0:
        print("Chưa có bài nào được gắn nhãn ER. Hãy chạy run_background.py trước.")
        sys.exit(1)

    print("1/3 Truy xuất bằng chứng...")
    run_id = retrieval.run(con, ticker, row["short_name"] or ticker, args.date_from)
    n = con.execute("select n_mention, n_bm25, n_top from screening_runs where run_id = ?", (run_id,)).fetchone()
    print(f"    run_id {run_id} | bài liên kết {n[0]} | có từ rủi ro {n[1]} | top {n[2]}")

    print("2/3 LLM đọc và xác nhận...")
    summary = llm_read.run(con, run_id, ticker, row)
    print(f"    xét {summary['depth']} bài đầu | đọc được {summary['n_read']} | rủi ro {summary['n_risk']} | lỗi {summary['n_error']}")
    for e in summary["errors"][:3]:
        print("    lỗi:", e)
    if summary["n_read"] == 0:
        print("LLM không đọc được bài nào, dừng lại để không xuất báo cáo rỗng sai. Kiểm tra API key, model, mạng.")
        sys.exit(1)

    print("3/3 Viết báo cáo...")
    report_md, events = report.build(con, run_id, ticker, row, prof, summary)
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.REPORT_DIR / f"{ticker}_run{run_id}.md"
    path.write_text(report_md, encoding="utf-8")
    bad = [e["headline"] for e in events if not e["check"]["trich_dan_hop_le"] or e["check"]["con_tieng_viet"]]
    print(f"    {len(events)} sự kiện | cần rà soát định dạng: {len(bad)}")
    print("Đã lưu:", path)


if __name__ == "__main__":
    main()
