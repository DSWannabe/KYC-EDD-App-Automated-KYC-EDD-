"""Chạy ER cho một nhóm bài: quét, tính feature, chấm điểm, ghi vào corpus.db."""
import pandas as pd

import config
import db
import er_model
from er_features import pair_features
from er_scan import scan_article

PAIR_COLS = ["article_id", "ticker", "f1_alias", "f2_ma_ck", "f3_lanh_dao", "f4_dia_ly", "f6_ty_le_loai",
             "f7_tieu_de", "f8_so_nhac_sach", "chi_alias_yeu", "xac_suat", "quyet_dinh", "model_version", "created_at"]
MENTION_COLS = ["article_id", "ticker", "alias", "chuoi_khop", "loai_alias", "start_pos", "end_pos",
                "trong_tieu_de", "ten_dai_hon", "luat_loai_tru", "sach"]


def extract(res, articles):
    """articles: DataFrame có cột id, title, cleaned_text. Trả về (mentions, pairs)."""
    mention_rows, pair_rows = [], []
    for r in articles.itertuples():
        full, mentions = scan_article(res, int(r.id), r.title, r.cleaned_text)
        mention_rows.extend(mentions)
        pair_rows.extend(pair_features(res, int(r.id), full, mentions))
    return pd.DataFrame(mention_rows, columns=MENTION_COLS), pd.DataFrame(pair_rows)


def label(bundle, pairs):
    if len(pairs) == 0:
        return pairs.assign(xac_suat=[], quyet_dinh=[], model_version=[], created_at=[])
    pairs = pairs.copy()
    pairs["xac_suat"] = er_model.predict(bundle, pairs).round(4)
    pairs["quyet_dinh"] = [er_model.decide(p, f8, bundle) for p, f8 in zip(pairs.xac_suat, pairs.f8_so_nhac_sach)]
    pairs["model_version"] = bundle["version"]
    pairs["created_at"] = db.now()
    return pairs


def save(con, articles, mentions, pairs, model_version):
    ids = [int(i) for i in articles["id"]]
    for k in range(0, len(ids), 900):
        part = ids[k:k + 900]
        con.execute(f"delete from er_mentions where article_id in ({db.placeholders(part)})", part)
        con.execute(f"delete from er_article_company where article_id in ({db.placeholders(part)})", part)

    con.executemany(f"insert into er_mentions values ({db.placeholders(MENTION_COLS)})",
                    mentions[MENTION_COLS].astype(object).values.tolist())
    con.executemany(f"insert into er_article_company values ({db.placeholders(PAIR_COLS)})",
                    pairs[PAIR_COLS].astype(object).values.tolist())

    n_mention = mentions.groupby("article_id").size().to_dict()
    n_company = pairs[pairs.quyet_dinh == "1"].groupby("article_id").size().to_dict()
    now = db.now()
    con.executemany("insert or replace into er_scan values (?, ?, ?, ?, ?, ?, ?)", [
        (i, h, int(n_mention.get(i, 0)), int(n_company.get(i, 0)), config.ER_RULE_VERSION, model_version, now)
        for i, h in zip(ids, articles["content_hash"])
    ])
    con.commit()


def articles_to_scan(con, model_version, rescan_all=False, limit=None):
    sql = """
        select a.id, a.title, a.cleaned_text, a.content_hash
        from articles a left join er_scan s on s.article_id = a.id
    """
    params = []
    if not rescan_all:
        sql += """
        where s.article_id is null
           or s.rule_version != ? or s.model_version != ?
           or ifnull(s.content_hash, '') != ifnull(a.content_hash, '')
        """
        params = [config.ER_RULE_VERSION, model_version]
    sql += " order by a.id"
    if limit:
        sql += f" limit {int(limit)}"
    return pd.read_sql(sql, con, params=params).fillna("")
