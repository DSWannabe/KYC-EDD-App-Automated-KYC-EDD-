"""Huấn luyện mô hình ER (Logistic Regression) từ dữ liệu đã gắn nhãn, lưu ra models/.

Nhãn:
- v12: mỗi bài một dòng, cột cong_ty_vn100_2026 (mọi cặp ứng viên của bài đều có nhãn)
- benchmark: mỗi cặp (article_id, ticker) một dòng, cột nhan (chỉ các cặp này có nhãn)

Chạy:
    python train_er.py --v12 articles_labeled_v12_full_relabel.csv --bench benchmark_vn100_can_bang.csv
    python train_er.py ... --eval     # chỉ đánh giá: huấn luyện trên v12 (bỏ bài benchmark), chấm trên benchmark
"""
import argparse

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

import config
import db
import er_model
from er_pipeline import extract
from er_resources import ErResources


def read_labels(v12_path, bench_path):
    v12 = pd.read_csv(v12_path, dtype=str, keep_default_na=False)
    gold_v12 = {(int(r.id), t) for r in v12.itertuples()
                for t in r.cong_ty_vn100_2026.split(";") if t and t != "no"}
    bench = pd.read_csv(bench_path, dtype={"nhan": str})
    bench_label = {(int(a), t): n == "1" for a, t, n in zip(bench.article_id, bench.ticker, bench.nhan)}
    return set(v12.id.astype(int)), gold_v12, bench_label


def load_articles(con, ids):
    ids = sorted(ids)
    parts = []
    for k in range(0, len(ids), 900):
        part = ids[k:k + 900]
        parts.append(pd.read_sql(f"select id, title, cleaned_text from articles where id in ({db.placeholders(part)})",
                                 con, params=part))
    return pd.concat(parts).fillna("")


def report(name, y, xs, nguong):
    du_doan = xs >= nguong
    gold = y.astype(bool)
    print(f"{name}: n={len(y)} | F1={er_model.f1_score(du_doan, gold):.3f} | "
          f"balanced_acc={balanced_accuracy_score(gold, du_doan):.3f} | AUC={roc_auc_score(gold, xs):.3f} | "
          f"bắt nhãn 0={(~du_doan & ~gold).sum() / max((~gold).sum(), 1):.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v12", required=True)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--version", default="lr_v1")
    ap.add_argument("--eval", action="store_true")
    args = ap.parse_args()

    v12_ids, gold_v12, bench_label = read_labels(args.v12, args.bench)
    bench_ids = {a for a, _ in bench_label}

    res = ErResources(db.companies())
    con = db.corpus()
    articles = load_articles(con, v12_ids | bench_ids)
    print(len(articles), "bài có nhãn tìm thấy trong corpus.db")

    _, pairs = extract(res, articles)
    keys = list(zip(pairs.article_id, pairs.ticker))

    # cặp thuộc bài v12: mọi cặp đều có nhãn; cặp chỉ thuộc benchmark: chỉ cặp được gắn
    pairs["nguon"] = ["bench" if k in bench_label else "v12" if k[0] in v12_ids else "" for k in keys]
    pairs["gold"] = [bench_label[k] if k in bench_label else k in gold_v12 for k in keys]
    pairs = pairs[pairs.nguon != ""].reset_index(drop=True)

    if args.eval:
        train_part = pairs[(pairs.nguon == "v12") & ~pairs.article_id.isin(bench_ids)].reset_index(drop=True)
        test_part = pairs[pairs.nguon == "bench"].reset_index(drop=True)
        bundle = er_model.train(train_part, train_part.gold.values.astype(int), args.version + "_eval")
        print("CV trên phần huấn luyện:", bundle["cv"], "| ngưỡng:", bundle["upper"])
        xs = er_model.predict(bundle, test_part)
        report("Benchmark", test_part.gold.values.astype(int), xs, bundle["upper"])
        return

    y = pairs.gold.values.astype(int)
    bundle = er_model.train(pairs, y, args.version)
    er_model.save(bundle, config.ER_MODEL_FILE)
    print("Số cặp huấn luyện:", len(y), "| tỷ lệ dương:", round(float(np.mean(y)), 3))
    print("CV:", bundle["cv"], "| ngưỡng trên:", bundle["upper"], "| ngưỡng dưới:", bundle["lower"])
    print("Đã lưu:", config.ER_MODEL_FILE)


if __name__ == "__main__":
    main()
