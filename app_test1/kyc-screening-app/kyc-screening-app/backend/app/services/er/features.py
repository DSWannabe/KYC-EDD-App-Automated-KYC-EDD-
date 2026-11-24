"""Feature của cặp (bài, công ty) cho ER nền (tương đương p04 của pipeline, không dùng LLM)."""
import math

from app.services.lookup.text import MAX_NHAC, lan_nhac, tim_ten, tu_ngu_canh

COT_SO = ["co_ticker", "co_ten_ngan", "so_lanh_dao", "log_so_nhac", "trong_tieu_de"]


def dac_trung_bai(full, do_dai_tieu_de, ticker, h):
    """full = tiêu đề + "\\n" + nội dung đã chuẩn hóa. h là dòng hồ sơ công ty. None nếu không thấy lần nhắc nào."""
    sp_ticker, sp_ten, sp = lan_nhac(full, ticker, h["ten_ngan"])
    if not sp:
        return None
    return {
        "co_ticker": int(len(sp_ticker) > 0),
        "co_ten_ngan": int(len(sp_ten) > 0),
        "so_lanh_dao": sum(1 for ten in h["lanh_dao"] if ten and tim_ten(full, ten)),
        "log_so_nhac": round(math.log1p(len(sp)), 4),
        "trong_tieu_de": int(any(s < do_dai_tieu_de for s, _ in sp)),
        "ngu_canh": " ".join(tu_ngu_canh(full, s, e) for s, e in sp[:MAX_NHAC]),
    }
