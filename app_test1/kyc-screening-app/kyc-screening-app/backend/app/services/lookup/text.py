"""Hàm văn bản và hồ sơ công ty cho tra cứu (sao nguyên từ ver3: common.py và truy_van.py)."""
import math
import re
import unicodedata

import pandas as pd

from app import config

SO_TU_DOAN = 30
MAX_NHAC = 5
TU_RE = re.compile(r"\w+|%|/")

DOI_DAU = {
    "oà": "òa", "oá": "óa", "oả": "ỏa", "oã": "õa", "oạ": "ọa",
    "oè": "òe", "oé": "óe", "oẻ": "ỏe", "oẽ": "õe", "oẹ": "ọe",
    "uỳ": "ùy", "uý": "úy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy",
}
DOI_DAU.update({k.capitalize(): v.capitalize() for k, v in DOI_DAU.items()})
DOI_DAU_RE = re.compile(r"(?<![qQ])(" + "|".join(DOI_DAU) + r")(?!\w)")


def chuan_hoa(text):
    # NFC, thống nhất vị trí dấu ("hoà" -> "hòa"), gộp khoảng trắng trong dòng
    text = unicodedata.normalize("NFC", str(text or ""))
    text = DOI_DAU_RE.sub(lambda m: DOI_DAU[m.group(1)], text)
    return re.sub(r"[ \t ]+", " ", text).strip()


def khong_dau(s):
    # Bỏ dấu, viết thường: "Hòa Phát" -> "hoa phat"
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", s.lower()).strip()


def tach(s):
    return [x.strip() for x in str(s or "").split(";") if x.strip()]


# ---------- Hồ sơ công ty ----------

def doc_ho_so(con_cong_ty):
    """Mỗi ticker một dòng: tên đầy đủ, tên ngắn, lãnh đạo, MST."""
    catalog = pd.read_sql(f'select ticker, company_name, key_leaders, tax_id from "{config.CATALOG}"', con_cong_ty)
    names = pd.read_sql("select * from company_names", con_cong_ty)
    cot_ten = [c for c in ["short_name", "aliases", "strong_aliases", "weak_aliases"] if c in names.columns]
    df = catalog.merge(names[["ticker"] + cot_ten], on="ticker", how="left").fillna("")

    def ten_ngan(r):
        out = {}
        for x in [t for c in cot_ten for t in tach(r[c])]:
            x = chuan_hoa(x)
            if x and x.upper() != r["ticker"] and x.lower() not in out:
                out[x.lower()] = x
        return list(out.values())

    def lanh_dao(s):
        return [chuan_hoa(re.sub(r"\(.*?\)", "", x)) for x in tach(s)]

    def goc_mst(s):
        # 10 số gốc, bỏ phần chi nhánh "-001"; MST 9 số thì thêm số 0 đầu
        so = re.sub(r"\D", "", str(s).split("-")[0])
        return so.zfill(10) if len(so) == 9 else so

    df["ten_ngan"] = df.apply(ten_ngan, axis=1)
    df["lanh_dao"] = df["key_leaders"].map(lanh_dao)
    df["mst"] = df["tax_id"].map(goc_mst)
    return df[["ticker", "company_name", "ten_ngan", "lanh_dao", "mst"]].set_index("ticker")


# ---------- Tìm lần nhắc ----------

def tim_ticker(full, ticker):
    # Mã: phân biệt hoa thường, có ranh giới từ
    return [m.span() for m in re.finditer(rf"(?<!\w){re.escape(ticker)}(?!\w)", full)]


def tim_ten(full, ten):
    # Tên: không phân biệt hoa thường, có ranh giới từ
    return [m.span() for m in re.finditer(rf"(?<!\w){re.escape(ten)}(?!\w)", full, re.IGNORECASE)]


def bo_long_nhau(spans):
    # Khoảng nằm trong khoảng dài hơn thì bỏ: "VNDirect" trong "Chứng khoán VNDirect"
    spans = sorted(set(spans), key=lambda x: (x[0], -(x[1] - x[0])))
    out = []
    for s, e in spans:
        if not any(s0 <= s and e <= e0 for s0, e0 in out):
            out.append((s, e))
    return out


def lan_nhac(full, ticker, ten_ngan):
    """Trả về (spans ticker, spans tên ngắn, spans gộp đã bỏ lồng nhau)."""
    sp_ticker = tim_ticker(full, ticker)
    sp_ten = [sp for ten in ten_ngan for sp in tim_ten(full, ten)]
    return sp_ticker, sp_ten, bo_long_nhau(sp_ticker + sp_ten)


def cat_doan(full, start, end, so_tu=SO_TU_DOAN):
    """Cắt so_tu từ mỗi bên quanh [start, end). Trả về đoạn và vị trí tên trong đoạn."""
    trai = " ".join(full[:start].split()[-so_tu:])
    phai = " ".join(full[end:].split()[:so_tu])
    ten = full[start:end]
    s = len(trai) + 1 if trai else 0
    doan = (trai + " " if trai else "") + ten + (" " + phai if phai else "")
    return doan, (s, s + len(ten))


def tu_ngu_canh(doan, start, end, so_tu=5):
    """Từ viết thường quanh lần nhắc, gắn tiền tố L_/R_ (cho TF-IDF)."""
    trai = TU_RE.findall(doan[:start].lower())[-so_tu:]
    phai = TU_RE.findall(doan[end:].lower())[:so_tu]
    return " ".join(["L_" + w for w in trai] + ["R_" + w for w in phai])


# ---------- Ứng viên và feature ----------

def chua_tu(lon, nho):
    return re.search(rf"(?<!\w){re.escape(nho)}(?!\w)", lon) is not None


def chi_muc_ten(ho_so):
    """ticker -> tập tên không dấu (mã, tên ngắn, tên pháp lý)."""
    return {t: {khong_dau(x) for x in [t, *h["ten_ngan"], h["company_name"]] if x}
            for t, h in ho_so.iterrows()}


def sinh_ung_vien(ten, chi_muc):
    """{ticker: 'chinh_xac' | 'mot_phan'} cho các công ty có tên khớp với tên người dùng đưa."""
    q = khong_dau(ten)
    kq = {}
    if len(q) < 2:
        return kq
    for t, cac_ten in chi_muc.items():
        if q in cac_ten:
            kq[t] = "chinh_xac"
        elif len(q) >= 3 and any(len(a) >= 3 and (chua_tu(a, q) or chua_tu(q, a)) for a in cac_ten):
            kq[t] = "mot_phan"
    return kq


def co_mst(doan, mst):
    # Đoạn có chứa MST của công ty (10 số gốc, viết liền hoặc có dấu cách/chấm)
    if not mst:
        return 0
    so = re.sub(r"[ .]", "", doan)
    cach_viet = {mst, mst.lstrip("0")}
    return int(any(re.search(rf"(?<!\d){x}(?!\d)", so) for x in cach_viet if len(x) >= 9))


def tim_vi_tri(doan, ten):
    sp = tim_ten(doan, ten)
    return sp[0] if sp else None


def dac_trung(doan, vi_tri, ticker, kieu_khop, h):
    """Feature của cặp (đoạn, ứng viên). h là dòng hồ sơ ứng viên, vi_tri là vị trí tên người dùng đưa."""
    sp_ticker, sp_ten, sp = lan_nhac(doan, ticker, h["ten_ngan"])
    nhac = sp if sp else [vi_tri]   # chỉ khớp một phần: lấy ngữ cảnh quanh tên người dùng đưa
    return {
        "co_ticker": int(len(sp_ticker) > 0),
        "co_ten_ngan": int(len(sp_ten) > 0),
        "so_lanh_dao": sum(1 for ten in h["lanh_dao"] if ten and tim_ten(doan, ten)),
        "log_so_nhac": round(math.log1p(len(sp)), 4),
        "khop_chinh_xac": int(kieu_khop == "chinh_xac"),
        "co_mst": co_mst(doan, h["mst"]),
        "ngu_canh": " ".join(tu_ngu_canh(doan, s, e) for s, e in nhac[:MAX_NHAC]),
    }
