"""Tra cứu: đoạn văn + tên công ty -> duy_nhat / can_xac_nhan / khong_co."""
from app.services.lookup import text
from app.services.lookup.model import MoHinh, quyet_dinh

_cache = {}


def _lay(con_cong_ty):
    # Hồ sơ và mô hình nạp một lần
    if not _cache:
        ho_so = text.doc_ho_so(con_cong_ty)
        _cache.update(ho_so=ho_so, chi_muc=text.chi_muc_ten(ho_so), mo_hinh=MoHinh())
    return _cache["ho_so"], _cache["chi_muc"], _cache["mo_hinh"]


def _tra_cuu_mot_ten(doan, ten, ho_so, chi_muc, mh):
    vi_tri = text.tim_vi_tri(doan, ten)
    if vi_tri is None:
        return {"ten": ten, "trang_thai": "khong_co", "ung_vien": [], "ghi_chu": "Không thấy tên trong đoạn văn"}
    uv = []
    for t, kieu in text.sinh_ung_vien(ten, chi_muc).items():
        d = text.dac_trung(doan, vi_tri, t, kieu, ho_so.loc[t])
        uv.append({"ticker": t, "co_mst": d["co_mst"], "diem": mh.diem(d)})
    trang_thai, ds = quyet_dinh(uv, mh.nguong_khong_co, mh.nguong_duy_nhat)
    diem = {u["ticker"]: u["diem"] for u in uv}
    return {"ten": ten, "trang_thai": trang_thai, "ghi_chu": "",
            "ung_vien": [{"ticker": t, "ten_cong_ty": ho_so.loc[t, "company_name"], "diem": round(diem[t], 3)} for t in ds]}


def tra_cuu(con_cong_ty, doan, ten=None):
    """ten=None: tự tìm mọi tên công ty có trong đoạn. Trả về list kết quả, mỗi tên một phần tử."""
    ho_so, chi_muc, mh = _lay(con_cong_ty)
    doan = text.chuan_hoa(doan)
    if not ten:
        ten = sorted({doan[s:e] for t, h in ho_so.iterrows() for s, e in text.lan_nhac(doan, t, h["ten_ngan"])[2]})
    return [_tra_cuu_mot_ten(doan, x, ho_so, chi_muc, mh) for x in ([ten] if isinstance(ten, str) else ten)]
