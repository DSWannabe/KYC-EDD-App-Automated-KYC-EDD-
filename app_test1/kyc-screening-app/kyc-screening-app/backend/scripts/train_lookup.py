"""Học lại mô hình lookup (q01, q02, q04 moi_ngu_canh, q05) rồi xuất models/lookup_model.json.

Chạy: python scripts/train_lookup.py --pipeline-dir <thư mục có p01_cap.csv, p01_bai.csv>
Cần scikit-learn (chỉ để học; lúc chạy app không cần).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config
from app.db import connection as db
from app.services.lookup import model as mh
from app.services.lookup import text

KHONG_CO = "KHONG_CO"
LUOI = np.round(np.arange(0.05, 1.0, 0.05), 2)
MUC_TIEU = 0.98


def tao_cap(pipeline_dir, ho_so, chi_muc):
    """q01 + q02: mỗi cặp benchmark thành một truy vấn, sinh ứng viên và feature."""
    cap = pd.read_csv(pipeline_dir / "p01_cap.csv")
    bai = pd.read_csv(pipeline_dir / "p01_bai.csv").fillna("")
    full_by_id = dict(zip(bai["article_id"], bai["full"]))
    tv, dong = [], []
    for r in cap.itertuples():
        full = full_by_id[r.article_id]
        s, e = text.lan_nhac(full, r.ticker, ho_so.loc[r.ticker, "ten_ngan"])[2][0]
        doan, vi_tri = text.cat_doan(full, s, e)
        qid = len(tv)
        dap_an = r.ticker if r.nhan == 1 else KHONG_CO
        tv.append({"query_id": qid, "article_id": r.article_id, "tap": r.tap, "dap_an": dap_an})
        for t, kieu in text.sinh_ung_vien(full[s:e], chi_muc).items():
            dong.append({"query_id": qid, "ticker": t, "la_dap_an": int(t == dap_an),
                         **text.dac_trung(doan, vi_tri, t, kieu, ho_so.loc[t])})
    return pd.DataFrame(tv), pd.DataFrame(dong).merge(pd.DataFrame(tv)[["query_id", "article_id", "tap"]], on="query_id")


def ma_tran(df, tfidf):
    return hstack([csr_matrix(df[mh.COT_SO].values.astype(float)), tfidf.transform(df["ngu_canh"])]).tocsr()


def fit(df):
    tfidf = TfidfVectorizer(token_pattern=r"\S+", lowercase=False, min_df=3, sublinear_tf=True).fit(df["ngu_canh"])
    model = LogisticRegression(max_iter=2000, class_weight="balanced").fit(ma_tran(df, tfidf), df["la_dap_an"])
    return tfidf, model


def diem_oof(dev):
    xs = np.zeros(len(dev))
    for tr, va in GroupKFold(n_splits=5).split(dev, groups=dev["article_id"]):
        tfidf, model = fit(dev.iloc[tr])
        xs[va] = model.predict_proba(ma_tran(dev.iloc[va], tfidf))[:, 1]
    return xs


def chay(tv, cap, nguong_kc, nguong_dn):
    """Quyết định cho mọi truy vấn của một tập. cap có cột diem."""
    nhom = dict(list(cap.groupby("query_id")))
    ket_qua = []
    for r in tv.itertuples():
        g = nhom.get(r.query_id)
        uv = [] if g is None else g[["ticker", "co_mst", "diem"]].to_dict("records")
        tt, ds = mh.quyet_dinh(uv, nguong_kc, nguong_dn)
        ket_qua.append({"dap_an": r.dap_an, "trang_thai": tt, "ds": ds, "dau": ds[0] if ds else KHONG_CO})
    return pd.DataFrame(ket_qua)


def chi_so(kq):
    co = kq["dap_an"] != KHONG_CO
    dn, nil = kq["trang_thai"] == "duy_nhat", kq["trang_thai"] == "khong_co"
    return {
        "dung_tra_loi_dau": (kq["dau"] == kq["dap_an"]).mean(),
        "recall_3": kq[co].apply(lambda r: r["dap_an"] in r["ds"], axis=1).mean(),
        "ty_le_duy_nhat": dn.mean(),
        "dung_khi_duy_nhat": (kq.loc[dn, "dau"] == kq.loc[dn, "dap_an"]).mean() if dn.any() else np.nan,
        "ty_le_can_xac_nhan": (kq["trang_thai"] == "can_xac_nhan").mean(),
        "precision_khong_co": (kq.loc[nil, "dap_an"] == KHONG_CO).mean() if nil.any() else np.nan,
        "recall_khong_co": nil[~co].mean(),
    }


def chon_nguong(tv_dev, dev):
    # Bước 1: ngưỡng "không có" cho tỉ lệ trả lời đầu đúng cao nhất (chưa trả lời duy nhất)
    dung = {n: chi_so(chay(tv_dev, dev, n, 1.1))["dung_tra_loi_dau"] for n in LUOI}
    kc = max(dung, key=dung.get)
    # Bước 2: ngưỡng "duy nhất" thấp nhất mà khi trả lời duy nhất vẫn đúng >= MUC_TIEU
    for n in LUOI[LUOI >= kc]:
        if chi_so(chay(tv_dev, dev, kc, n))["dung_khi_duy_nhat"] >= MUC_TIEU:
            return kc, n
    return kc, 1.1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline-dir", required=True)
    a = ap.parse_args()
    pdir = Path(a.pipeline_dir)

    con = db.company()
    ho_so = text.doc_ho_so(con)
    con.close()
    chi_muc = text.chi_muc_ten(ho_so)

    tv, cap = tao_cap(pdir, ho_so, chi_muc)
    cap["ngu_canh"] = cap["ngu_canh"].fillna("")
    dev, test = (cap[cap["tap"] == t].reset_index(drop=True) for t in ["dev", "test"])
    tv_dev, tv_test = (tv[tv["tap"] == t] for t in ["dev", "test"])
    print("truy vấn dev/test:", len(tv_dev), len(tv_test), "| cặp dev/test:", len(dev), len(test))

    dev["diem"] = diem_oof(dev)           # điểm dev là out-of-fold, để chọn ngưỡng không bị lạc quan
    kc, dn = chon_nguong(tv_dev, dev)
    print("ngưỡng không có / duy nhất:", kc, dn, "(tham chiếu q05: 0.40 / 0.80)")

    tfidf, model = fit(dev)
    test["diem"] = model.predict_proba(ma_tran(test, tfidf))[:, 1]
    print(pd.Series(chi_so(chay(tv_test, test, kc, dn))).round(3).to_string())
    print("(tham chiếu q05 test: dung_tra_loi_dau 0.880, recall_3 0.975, ty_le_duy_nhat 0.441, dung_khi_duy_nhat 0.975)")

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    mh.xuat_json(tfidf, model, mh.COT_SO, nguong_khong_co=kc, nguong_duy_nhat=dn)
    print("đã lưu", mh.FILE)


if __name__ == "__main__":
    main()
