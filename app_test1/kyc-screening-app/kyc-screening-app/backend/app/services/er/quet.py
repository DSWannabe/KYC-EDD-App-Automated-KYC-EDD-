"""Sinh ứng viên cho ER: quét bài mới, tìm công ty được nhắc (tầng 2-3 của luồng nền).

Dùng đúng cách tìm tên mà mô hình ER đã học (text.lan_nhac): mã phân biệt hoa thường,
tên ngắn và alias không phân biệt, bỏ span lồng nhau. Không có luật tay cho mã riêng nào.
Ghi vào article_scan_v3 (bài đã quét) và article_company_v3 (cặp bài, ticker và số lần nhắc).
"""
from datetime import datetime, timezone

from app.services.lookup import text


def quet_bai_moi(con, ho_so):
    """ho_so: kết quả text.doc_ho_so. Trả về số bài vừa quét. Chạy lại chỉ xử lý bài chưa quét."""
    bai_moi = con.execute("""
        select id, title, cleaned_text from articles
        where id not in (select article_id from article_scan_v3)
    """).fetchall()

    bay_gio = datetime.now(timezone.utc).isoformat()
    for article_id, title, noi_dung in bai_moi:
        full = text.chuan_hoa(title) + "\n" + text.chuan_hoa(noi_dung)
        thuong = full.lower()

        cong_ty = {}
        for ticker, h in ho_so.iterrows():
            # Lọc nhanh bằng tìm chuỗi con trước khi chạy regex
            if ticker not in full and not any(t.lower() in thuong for t in h["ten_ngan"]):
                continue
            sp = text.lan_nhac(full, ticker, h["ten_ngan"])[2]
            if sp:
                cong_ty[ticker] = len(sp)

        con.execute("insert into article_scan_v3 values (?, ?, ?)", (int(article_id), len(cong_ty), bay_gio))
        for ticker, so_lan in cong_ty.items():
            con.execute("insert into article_company_v3 values (?, ?, ?)", (int(article_id), ticker, so_lan))
    con.commit()
    return len(bai_moi)
