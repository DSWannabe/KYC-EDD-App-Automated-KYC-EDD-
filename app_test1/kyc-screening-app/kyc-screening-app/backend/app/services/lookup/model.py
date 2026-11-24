"""Mô hình chấm điểm cặp (đoạn, ứng viên): TF-IDF + hồi quy logistic, lưu bằng JSON để không phụ thuộc phiên bản sklearn."""
import json
import math
from collections import Counter

import numpy as np

from app import config

FILE = config.MODELS_DIR / "lookup_model.json"
COT_SO = ["co_ticker", "co_ten_ngan", "so_lanh_dao", "log_so_nhac", "khop_chinh_xac"]
KHOANG_CACH = 0.3


def xuat_json(tfidf, model, cot_so, duong_dan=FILE, **nguong):
    """Chuyển TfidfVectorizer + LogisticRegression của sklearn sang JSON. nguong: các ngưỡng đi kèm mô hình."""
    d = {
        "cot_so": cot_so,
        "vocab": {t: int(i) for t, i in tfidf.vocabulary_.items()},
        "idf": [float(x) for x in tfidf.idf_],
        "he_so_so": [float(x) for x in model.coef_[0][:len(cot_so)]],
        "he_so_tu": [float(x) for x in model.coef_[0][len(cot_so):]],
        "intercept": float(model.intercept_[0]),
        **{k: float(v) for k, v in nguong.items()},
    }
    duong_dan.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


class MoHinh:
    def __init__(self, duong_dan=FILE):
        d = json.loads(duong_dan.read_text(encoding="utf-8"))
        self.cot_so = d["cot_so"]
        self.vocab, self.idf = d["vocab"], d["idf"]
        self.w_so, self.w_tu = np.array(d["he_so_so"]), d["he_so_tu"]
        self.b = d["intercept"]
        self.nguong = {k: v for k, v in d.items() if k.startswith("nguong")}
        self.nguong_khong_co, self.nguong_duy_nhat = d.get("nguong_khong_co"), d.get("nguong_duy_nhat")

    def diem(self, dong):
        """dong: dict feature của một cặp. Trả về xác suất đúng công ty."""
        # TF-IDF giống sklearn: tf = 1 + log(đếm), nhân idf, chuẩn hóa L2
        dem = Counter(t for t in dong["ngu_canh"].split() if t in self.vocab)
        v = {self.vocab[t]: (1 + math.log(c)) * self.idf[self.vocab[t]] for t, c in dem.items()}
        chuan = math.sqrt(sum(x * x for x in v.values())) or 1.0
        z = self.b + float(np.dot(self.w_so, [float(dong[c]) for c in self.cot_so]))
        z += sum(self.w_tu[i] * x / chuan for i, x in v.items())
        return 1 / (1 + math.exp(-z))


def quyet_dinh(ung_vien, nguong_khong_co, nguong_duy_nhat):
    """ung_vien: list dict có 'ticker', 'co_mst', 'diem'. Trả về (trạng thái, danh sách ticker)."""
    if not ung_vien:
        return "khong_co", []
    mst = [u["ticker"] for u in ung_vien if u["co_mst"] == 1]
    if len(mst) == 1:                       # MST trong đoạn khớp đúng một công ty
        return "duy_nhat", mst
    xep = sorted(ung_vien, key=lambda u: -u["diem"])
    top1 = xep[0]["diem"]
    top2 = xep[1]["diem"] if len(xep) > 1 else 0.0
    if top1 < nguong_khong_co:
        return "khong_co", []
    if top1 >= nguong_duy_nhat and top1 - top2 >= KHOANG_CACH:
        return "duy_nhat", [xep[0]["ticker"]]
    return "can_xac_nhan", [u["ticker"] for u in xep if u["diem"] >= nguong_khong_co][:3]
