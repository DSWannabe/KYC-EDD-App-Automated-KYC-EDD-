"""ER bước 3: gộp lần nhắc theo cặp (bài, ticker), tính f1-f8 và từ ngữ cảnh."""
import math
import re

import config

HANG_ALIAS = {"strong": 3, "weak": 2, "ticker": 1}
TU_RE = re.compile(r"\w+|%|/")


def co_ma_ck(ticker, full):
    mau = rf"(mã chứng khoán|mã CK|MCK|mã|cổ phiếu|cp|HoSE|HOSE|HNX|UPCoM)\s*:?\s*{ticker}\b"
    return bool(re.search(mau, full))


def trong_danh_sach_ma(ticker, starts, ticker_spots, khoang_cach=15):
    khac = [s for s, t in ticker_spots if t != ticker]
    return any(abs(s - s0) <= khoang_cach for s0 in starts for s in khac)


def co_ten(full_lower, danh_sach):
    return any(re.search(rf"(?<!\w){re.escape(t.lower())}(?!\w)", full_lower) for t in danh_sach)


def tu_ngu_canh(full, start, end):
    trai = TU_RE.findall(full[max(0, start - 150): start].lower())[-config.CONTEXT_WORDS:]
    phai = TU_RE.findall(full[end: end + 150].lower())[:config.CONTEXT_WORDS]
    return " ".join(["L_" + t for t in trai] + ["R_" + t for t in phai])


def pair_features(res, article_id, full, mentions):
    full_lower = full.lower()
    ticker_spots = [(m["start_pos"], m["ticker"]) for m in mentions if m["loai_alias"] == "ticker"]

    by_ticker = {}
    for m in mentions:
        by_ticker.setdefault(m["ticker"], []).append(m)

    rows = []
    for ticker, ms in by_ticker.items():
        sach = [m for m in ms if m["sach"]]
        ticker_starts = [m["start_pos"] for m in sach if m["loai_alias"] == "ticker"]
        ngu_canh = [tu_ngu_canh(full, m["start_pos"], m["end_pos"])
                    for m in sorted(ms, key=lambda m: m["start_pos"])[:config.MAX_MENTIONS]]
        rows.append({
            "article_id": article_id,
            "ticker": ticker,
            "f1_alias": max((HANG_ALIAS[m["loai_alias"]] for m in sach), default=0),
            "f2_ma_ck": co_ma_ck(ticker, full) or trong_danh_sach_ma(ticker, ticker_starts, ticker_spots),
            "f3_lanh_dao": co_ten(full_lower, res.leaders.get(ticker, [])),
            "f4_dia_ly": co_ten(full_lower, res.provinces.get(ticker, [])),
            "f6_ty_le_loai": round(1 - len(sach) / len(ms), 2),
            "f7_tieu_de": any(m["trong_tieu_de"] for m in sach),
            "f8_so_nhac_sach": len(sach),
            "chi_alias_yeu": all(m["loai_alias"] in ("weak", "ticker") for m in ms),
            "ngu_canh": " ".join(ngu_canh),
        })
    return rows


def numeric_row(r):
    return [
        int(r["f1_alias"] == 3),
        int(r["f1_alias"] == 2),
        int(r["f1_alias"] == 1),
        int(r["f2_ma_ck"]),
        int(r["f3_lanh_dao"]),
        int(r["f4_dia_ly"]),
        float(r["f6_ty_le_loai"]),
        int(r["f7_tieu_de"]),
        math.log1p(r["f8_so_nhac_sach"]),
    ]


NUMERIC_NAMES = ["alias_strong", "alias_weak", "alias_ticker", "f2_ma_ck", "f3_lanh_dao",
                 "f4_dia_ly", "f6_ty_le_loai", "f7_tieu_de", "f8_log_so_nhac"]
