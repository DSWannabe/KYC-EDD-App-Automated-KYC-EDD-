"""Job nền: gắn nhãn ER cho các bài chưa xử lý, rồi tính vector cho bài có nhắc công ty.

Chạy sau mỗi lần crawler đổ bài vào corpus.db:
    python run_background.py
    python run_background.py --no-embed     # chỉ chạy ER
    python run_background.py --rescan       # quét lại toàn bộ (sau khi đổi alias, luật, mô hình)
"""
import argparse
import time

import config
import db
import embeddings
import er_model
import er_pipeline
from er_resources import ErResources


def run_er(con, rescan_all=False):
    bundle = er_model.load(config.ER_MODEL_FILE)
    todo = er_pipeline.articles_to_scan(con, bundle["version"], rescan_all)
    print(f"ER | mô hình {bundle['version']}, luật {config.ER_RULE_VERSION} | số bài cần xử lý: {len(todo)}")
    if len(todo) == 0:
        return

    res = ErResources(db.companies())
    t0 = time.time()
    for start in range(0, len(todo), config.ER_BATCH):
        part = todo.iloc[start:start + config.ER_BATCH]
        mentions, pairs = er_pipeline.extract(res, part)
        pairs = er_pipeline.label(bundle, pairs)
        er_pipeline.save(con, part, mentions, pairs, bundle["version"])
        print(f"  {min(start + config.ER_BATCH, len(todo))}/{len(todo)} bài | {time.time() - t0:.0f}s")


def summary(con):
    rows = con.execute("""
        select quyet_dinh, count(*) from er_article_company group by quyet_dinh order by quyet_dinh
    """).fetchall()
    n_article = con.execute("select count(*) from er_scan").fetchone()[0]
    print("Tổng số bài đã quét:", n_article, "| cặp theo quyết định:", dict(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-embed", action="store_true")
    ap.add_argument("--rescan", action="store_true")
    args = ap.parse_args()

    con = db.corpus()
    run_er(con, args.rescan)
    if not args.no_embed:
        embeddings.compute_missing(con)
    summary(con)


if __name__ == "__main__":
    main()
