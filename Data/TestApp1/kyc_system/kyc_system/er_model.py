"""ER bước 4: Logistic Regression trên f1-f8 + từ ngữ cảnh (cấu hình er_05)."""
import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import GroupKFold

import config
from er_features import NUMERIC_NAMES, numeric_row


def make_matrix(pairs, tfidf):
    so = csr_matrix(np.array([numeric_row(r) for _, r in pairs.iterrows()], dtype=float))
    chu = tfidf.transform(pairs["ngu_canh"])
    return hstack([so, chu]).tocsr()


def new_tfidf():
    return TfidfVectorizer(token_pattern=r"\S+", lowercase=False, min_df=3, sublinear_tf=True)


def f1_score(du_doan, gold):
    tp = (du_doan & gold).sum()
    fp = (du_doan & ~gold).sum()
    fn = (~du_doan & gold).sum()
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return 2 * p * r / (p + r) if p + r else 0


def xac_suat_cross_val(pairs, y, so_phan=5):
    xac_suat = np.zeros(len(y))
    for train, val in GroupKFold(n_splits=so_phan).split(pairs, y, pairs["article_id"]):
        tfidf = new_tfidf().fit(pairs["ngu_canh"].iloc[train])
        m = LogisticRegression(max_iter=2000)
        m.fit(make_matrix(pairs.iloc[train], tfidf), y[train])
        xac_suat[val] = m.predict_proba(make_matrix(pairs.iloc[val], tfidf))[:, 1]
    return xac_suat


def chon_nguong(xac_suat, y):
    gold = y.astype(bool)
    bang = [(round(n, 2), f1_score(xac_suat >= n, gold)) for n in np.arange(0.1, 0.91, 0.05)]
    return max(bang, key=lambda x: x[1])


def train(pairs, y, version):
    xs_cv = xac_suat_cross_val(pairs, y)
    nguong, f1_cv = chon_nguong(xs_cv, y)

    tfidf = new_tfidf().fit(pairs["ngu_canh"])
    model = LogisticRegression(max_iter=2000).fit(make_matrix(pairs, tfidf), y)

    cv = {
        "f1": round(float(f1_cv), 3),
        "auc": round(roc_auc_score(y, xs_cv), 3),
        "balanced_accuracy": round(balanced_accuracy_score(y, xs_cv >= nguong), 3),
        "n_pairs": int(len(y)),
        "ty_le_duong": round(float(y.mean()), 3),
    }
    return {"version": version, "tfidf": tfidf, "model": model, "upper": float(nguong),
            "lower": config.ER_LOWER, "feature_names": NUMERIC_NAMES + list(tfidf.get_feature_names_out()),
            "cv": cv}


def save(bundle, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)


def load(path):
    return joblib.load(path)


def predict(bundle, pairs):
    if len(pairs) == 0:
        return np.array([])
    return bundle["model"].predict_proba(make_matrix(pairs, bundle["tfidf"]))[:, 1]


def decide(xac_suat, f8, bundle):
    if f8 == 0:
        return "0"
    if xac_suat >= bundle["upper"]:
        return "1"
    if xac_suat < bundle["lower"]:
        return "0"
    return "xem"
