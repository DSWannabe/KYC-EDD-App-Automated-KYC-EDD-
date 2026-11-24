"""Học mô hình ER nền (pipeline p04 + p05, cấu hình lr_ngu_canh, không LLM) rồi xuất models/er_model.json.

Chạy: python scripts/train_er.py --pipeline-dir <thư mục có p01_cap.csv, p01_bai.csv>
Cần scikit-learn và scipy (chỉ để học).
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config
from app.db import connection as db
from app.services.er import label
from app.services.er.features import COT_SO, dac_trung_bai
from app.services.lookup import model as mh
from app.services.lookup import text


def ma_tran(df, tfidf):
    return hstack([csr_matrix(df[COT_SO].values.astype(float)), tfidf.transform(df["ngu_canh"])]).tocsr()


def fit(df):
    tfidf = TfidfVectorizer(token_pattern=r"\S+", lowercase=False, min_df=3, sublinear_tf=True).fit(df["ngu_canh"])
    model = LogisticRegression(max_iter=2000, class_weight="balanced").fit(ma_tran(df, tfidf), df["nhan"])
    return tfidf, model

MUC_TIEU = 0.95   # balanced accuracy của LR trên các cặp nằm ngoài vùng xem lại

def chon_vung_xem_lai(xs, y, nguong):
    """Vùng hẹp nhất quanh ngưỡng sao cho các cặp ngoài vùng đạt MUC_TIEU. Trả về (thấp, cao, tỷ lệ cặp trong vùng)."""
    for rong in np.arange(0.05, 0.51, 0.05):
        thap, cao = round(max(nguong - rong, 0), 2), round(min(nguong + rong, 1), 2)
        ngoai = (xs < thap) | (xs > cao)
        if len(set(y[ngoai])) < 2:
            break
        if balanced_accuracy_score(y[ngoai], xs[ngoai] >= nguong) >= MUC_TIEU:
            return thap, cao, 1 - ngoai.mean()
    return 0.0, 1.0, 1.0   # không đạt mục tiêu: mọi cặp đều đưa LLM

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline-dir", required=True)
    pdir = Path(ap.parse_args().pipeline_dir)

    con = db.company()
    ho_so = text.doc_ho_so(con)
    con.close()
    cap = pd.read_csv(pdir / "p01_cap.csv")
    bai = pd.read_csv(pdir / "p01_bai.csv").fillna("")
    full = dict(zip(bai["article_id"], bai["full"]))
    do_dai = dict(zip(bai["article_id"], bai["title"].str.len()))

    dong = [dac_trung_bai(full[r.article_id], do_dai[r.article_id], r.ticker, ho_so.loc[r.ticker]) for r in cap.itertuples()]
    data = pd.concat([cap[["article_id", "ticker", "tap", "nhan"]].reset_index(drop=True), pd.DataFrame(dong)], axis=1)
    dev, test = (data[data["tap"] == t].reset_index(drop=True) for t in ["dev", "test"])

    # Ngưỡng: balanced accuracy cao nhất trên điểm out-of-fold của dev
    xs = np.zeros(len(dev))
    for tr, va in GroupKFold(n_splits=5).split(dev, groups=dev["article_id"]):
        tfidf, model = fit(dev.iloc[tr])
        xs[va] = model.predict_proba(ma_tran(dev.iloc[va], tfidf))[:, 1]
    bang = [(round(n, 2), balanced_accuracy_score(dev["nhan"], xs >= n)) for n in np.arange(0.1, 0.91, 0.05)]
    nguong = max(bang, key=lambda x: x[1])[0]
    thap, cao, ty_le = chon_vung_xem_lai(xs, dev["nhan"].values, nguong)
    print(f"vùng xem lại: [{thap}, {cao}] | tỷ lệ cặp đưa LLM trên dev: {ty_le:.1%}")

    tfidf, model = fit(dev)
    p = model.predict_proba(ma_tran(test, tfidf))[:, 1]
    print("ngưỡng:", nguong, "| auc dev cv:", round(roc_auc_score(dev["nhan"], xs), 3),
          "| auc test:", round(roc_auc_score(test["nhan"], p), 3),
          "| balanced acc test:", round(balanced_accuracy_score(test["nhan"], p >= nguong), 3))

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    mh.xuat_json(tfidf, model, COT_SO, duong_dan=label.FILE, nguong=nguong)
    # Ghi phiên bản: lần chạy nền sau thấy phiên bản mới sẽ chấm lại mọi cặp
    d = json.loads(label.FILE.read_text(encoding="utf-8"))
    d["phien_ban"] = f"lr_ngu_canh_{datetime.now():%Y%m%d_%H%M}"
    d["xem_lai_thap"], d["xem_lai_cao"] = thap, cao
    label.FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print("đã lưu", label.FILE, "| phiên bản:", d["phien_ban"])


if __name__ == "__main__":
    main()
