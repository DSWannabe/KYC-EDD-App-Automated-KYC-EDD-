"""Hàm dùng chung cho tra cứu tự do: đoạn văn + tên công ty -> ứng viên -> feature."""
import math
import re
import unicodedata

from common import TU_RE, lan_nhac, tim_ten, tu_ngu_canh

SO_TU_DOAN = 30
MAX_NHAC = 5
DO_RONG_THEM = (10, 20, 30)   # các cửa sổ từ ngữ cảnh rộng hơn ±5 để so sánh ở q04


def khong_dau(s):
    # Bỏ dấu, viết thường, gộp khoảng trắng: "Hòa Phát" -> "hoa phat"
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", s.lower()).strip()


def chua_tu(lon, nho):
    # "nho" nằm trong "lon" với ranh giới từ
    return re.search(rf"(?<!\w){re.escape(nho)}(?!\w)", lon) is not None


# ---------- Ứng viên ----------

def chi_muc_ten(ho_so):
    """ticker -> danh sách tên không dấu (mã, tên ngắn, tên pháp lý)."""
    return {t: {khong_dau(x) for x in [t, *h["ten_ngan"], h["company_name"]] if x}
            for t, h in ho_so.iterrows()}


def sinh_ung_vien(ten, chi_muc):
    """Trả về {ticker: 'chinh_xac' | 'mot_phan'} cho các công ty có tên khớp với tên người dùng đưa."""
    q = khong_dau(ten)
    ket_qua = {}
    if len(q) < 2:
        return ket_qua
    for t, cac_ten in chi_muc.items():
        if q in cac_ten:
            ket_qua[t] = "chinh_xac"
        elif len(q) >= 3 and any(len(a) >= 3 and (chua_tu(a, q) or chua_tu(q, a)) for a in cac_ten):
            ket_qua[t] = "mot_phan"
    return ket_qua


# ---------- Đoạn văn ----------

def cat_doan(full, start, end, so_tu=SO_TU_DOAN):
    """Cắt so_tu từ mỗi bên quanh [start, end). Trả về đoạn và vị trí tên trong đoạn."""
    trai = " ".join(full[:start].split()[-so_tu:])
    phai = " ".join(full[end:].split()[:so_tu])
    ten = full[start:end]
    s = len(trai) + 1 if trai else 0
    doan = (trai + " " if trai else "") + ten + (" " + phai if phai else "")
    return doan, (s, s + len(ten))


def tim_vi_tri(doan, ten):
    # Vị trí đầu tiên của tên trong đoạn (không phân biệt hoa thường), None nếu không thấy
    sp = tim_ten(doan, ten)
    return sp[0] if sp else None


def che_khoang(text, spans, nhan="[CÔNG TY]"):
    """Thay các khoảng [start, end) bằng nhãn chung, để embedding đo ngữ cảnh chứ không đo tên."""
    for s, e in sorted(set(spans), reverse=True):
        text = text[:s] + nhan + text[e:]
    return text


def co_mst(doan, mst):
    # Đoạn có chứa MST của công ty (10 số gốc, có thể viết liền hoặc có dấu cách/chấm)
    if not mst:
        return 0
    so = re.sub(r"[ .]", "", doan)
    cach_viet = {mst, mst.lstrip("0")}   # MST bắt đầu bằng 0 hay bị viết thiếu số 0
    return int(any(re.search(rf"(?<!\d){x}(?!\d)", so) for x in cach_viet if len(x) >= 9))


# ---------- Feature của cặp (đoạn, ứng viên) ----------

def tu_ngu_canh_rong(doan, start, end, so_tu):
    """Như tu_ngu_canh nhưng không giới hạn 150 ký tự, lấy đủ so_tu từ mỗi bên."""
    trai = TU_RE.findall(doan[:start].lower())[-so_tu:]
    phai = TU_RE.findall(doan[end:].lower())[:so_tu]
    return " ".join(["L_" + w for w in trai] + ["R_" + w for w in phai])


def dac_trung(doan, vi_tri, ticker, kieu_khop, h):
    """h là dòng hồ sơ của ứng viên. vi_tri là vị trí tên người dùng đưa trong đoạn."""
    sp_ticker, sp_ten, sp = lan_nhac(doan, ticker, h["ten_ngan"])
    nhac = sp if sp else [vi_tri]   # ứng viên chỉ khớp một phần: lấy ngữ cảnh quanh tên người dùng đưa
    rong = {f"ngu_canh_{w}": " ".join(tu_ngu_canh_rong(doan, s, e, w) for s, e in nhac[:MAX_NHAC])
            for w in DO_RONG_THEM}
    return {
        "co_ticker": int(len(sp_ticker) > 0),
        "co_ten_ngan": int(len(sp_ten) > 0),
        "so_lanh_dao": sum(1 for ten in h["lanh_dao"] if ten and tim_ten(doan, ten)),
        "log_so_nhac": round(math.log1p(len(sp)), 4),
        "trong_tieu_de": 0,                        # đoạn dán vào không có tiêu đề
        "khop_chinh_xac": int(kieu_khop == "chinh_xac"),
        "co_mst": co_mst(doan, h["mst"]),
        "ngu_canh": " ".join(tu_ngu_canh(doan, s, e) for s, e in nhac[:MAX_NHAC]),
        **rong,
    }
