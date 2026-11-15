"""Truy xuất bằng chứng rủi ro cho một công ty (port từ prod_02, cấu hình pipeline_v1).

Khác prod_02: danh sách bài của công ty và số công ty trong bài lấy từ kết quả ER (er_article_company),
thay vì so khớp regex.
"""
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

import config
import db

RISK_PHRASES_V2 = [
    "vi phạm", "sai phạm", "xử phạt", "bị phạt", "khởi tố", "bị bắt", "bắt giữ", "tạm giam",
    "truy tố", "điều tra", "thanh tra", "lừa đảo", "chiếm đoạt", "tham ô", "hối lộ",
    "tranh chấp", "khởi kiện", "phá sản", "đình chỉ", "cưỡng chế", "ô nhiễm",
    "thua lỗ", "báo lỗ", "lỗ ròng", "giảm lãi", "lãi giảm", "lợi nhuận giảm", "sụt giảm", "đi lùi",
    "nợ xấu", "giải chấp", "sự cố", "tai nạn", "cướp", "mạo danh", "giả mạo", "tin đồn",
    "từ nhiệm", "miễn nhiệm", "bổ nhiệm", "từ chức", "chủ tịch mới", "tổng giám đốc mới",
    "ceo", "thay chủ tịch", "thay tổng giám đốc", "rời ghế",
    "phiên tòa", "hình sự", "xét xử", "tuyên án", "cáo trạng", "truy thu", "vụ kiện", "nguyên đơn",
    "đồng phạm", "phạm tội", "tố tụng", "sơ thẩm", "vụ án", "cáo buộc", "bị cáo", "bộ luật",
    "chứng cứ", "thay máu", "cựu ceo", "đơn từ nhiệm", "trái quy định",
]

RISK_QUERIES = [
    "doanh nghiệp bị khởi tố, điều tra, xử phạt vì vi phạm pháp luật",
    "công ty bị kiện, tranh chấp tại tòa án",
    "doanh nghiệp thua lỗ, lợi nhuận giảm mạnh, nợ xấu, khó khăn tài chính",
    "chủ tịch, tổng giám đốc từ nhiệm, bị miễn nhiệm, thay đổi lãnh đạo",
    "sự cố, bị cướp, bị mạo danh, lừa đảo, tin đồn ảnh hưởng doanh nghiệp",
]

RISK_TEXT = "gặp rủi ro: vi phạm, bị điều tra, kiện tụng, thua lỗ, lợi nhuận giảm, nợ xấu, thay đổi lãnh đạo, sự cố"


# ---------- BM25 v2 ----------

def tokenize(text):
    return re.findall(r"\w+", unicodedata.normalize("NFC", str(text)).lower())


def tokenize_bigram(text):
    words = tokenize(text)
    return words + [a + "_" + b for a, b in zip(words, words[1:])]


def phrase_tokens(phrases):
    out = []
    for p in phrases:
        words = tokenize(p)
        out += words if len(words) == 1 else [a + "_" + b for a, b in zip(words, words[1:])]
    return out


class BM25:
    def __init__(self, docs, k1=1.2, b=0.75):
        self.k1, self.b = k1, b
        self.N = len(docs)
        self.doc_len = np.array([len(d) for d in docs])
        self.avgdl = self.doc_len.mean()
        self.index = defaultdict(dict)
        for i, d in enumerate(docs):
            for term, tf in Counter(d).items():
                self.index[term][i] = tf
        self.idf = {t: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.index.items()}

    def score(self, query_tokens):
        scores = np.zeros(self.N)
        for term in set(query_tokens):
            for i, tf in self.index.get(term, {}).items():
                norm = 1 - self.b + self.b * self.doc_len[i] / self.avgdl
                scores[i] += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return scores


# ---------- dữ liệu ----------

def included_decisions():
    return ("1", "xem") if config.ER_INCLUDE_REVIEW else ("1",)


def load_docs(con):
    # toàn bộ bài đã quét ER (BM25 cần cả kho để tính IDF)
    decisions = included_decisions()
    docs = pd.read_sql(f"""
        select a.id, a.title, a.cleaned_text, a.published_at,
               (select count(*) from er_article_company p
                where p.article_id = a.id and p.quyet_dinh in ({db.placeholders(decisions)})) as n_company
        from articles a join er_scan s on s.article_id = a.id
    """, con, params=list(decisions))
    docs["title"] = docs["title"].fillna("")
    docs["cleaned_text"] = docs["cleaned_text"].fillna("")
    docs["n_company"] = docs["n_company"].clip(lower=1)
    return docs


def company_docs(con, ticker, date_from=None):
    decisions = included_decisions()
    sql = f"""
        select p.article_id from er_article_company p join articles a on a.id = p.article_id
        where p.ticker = ? and p.quyet_dinh in ({db.placeholders(decisions)})
    """
    params = [ticker, *decisions]
    if date_from:
        sql += " and a.published_at >= ?"
        params.append(date_from)
    return {r[0] for r in con.execute(sql, params)}


# ---------- các bước xếp hạng ----------

def bm25_ranking(docs, ids):
    bm25 = BM25([tokenize_bigram(t + " " + b) for t, b in zip(docs["title"], docs["cleaned_text"])])
    score = bm25.score(phrase_tokens(RISK_PHRASES_V2)) / docs["n_company"].values ** config.PENALTY
    by_id = dict(zip(docs["id"], score))
    keep = [d for d in ids if by_id.get(d, 0) > 0]   # bỏ bài không có từ rủi ro nào
    return sorted(keep, key=lambda d: -by_id[d])


def dense_ranking(con, ids, n_company):
    if not ids:
        return []
    from embeddings import load_encoder, free_gpu
    encoder = load_encoder()
    query_vecs = np.asarray(encoder.encode(RISK_QUERIES, normalize_embeddings=True), dtype=np.float32)
    del encoder
    free_gpu()

    ids = list(ids)
    best = {}
    for k in range(0, len(ids), 900):
        part = ids[k:k + 900]
        rows = con.execute(f"select article_id, vec from chunk_vectors where article_id in ({db.placeholders(part)})",
                           part).fetchall()
        if not rows:
            continue
        vecs = np.stack([np.frombuffer(v, dtype=np.float16).astype(np.float32) for _, v in rows])
        for (d, _), s in zip(rows, (vecs @ query_vecs.T).max(axis=1)):
            best[d] = max(best.get(d, -1.0), float(s))
    score = {d: s - config.LAM * math.log(n_company[d]) for d, s in best.items()}
    return sorted(score, key=lambda d: -score[d])


def rrf(run_bm25, run_dense):
    fused = defaultdict(float)
    for rank, d in enumerate(run_bm25):
        fused[d] += 1 / (config.RRF_K + rank + 1)
    for rank, d in enumerate(run_dense):
        fused[d] += config.W / (config.RRF_K + rank + 1)
    return sorted(fused, key=lambda d: -fused[d])


def cross_encoder_scores(con, ticker, short_name, top, info):
    ce = {d: s for d, s in con.execute("select article_id, score from ce_scores where ticker = ?", (ticker,))}
    need = [d for d in top if d not in ce]
    if need:
        from sentence_transformers import CrossEncoder
        from embeddings import free_gpu
        reranker = CrossEncoder(config.RERANK_MODEL, max_length=512, device=config.DEVICE)
        if config.DEVICE == "cuda":
            reranker.model.half()
        pairs = [(f"{short_name} {RISK_TEXT}", info.loc[d, "title"] + ". " + info.loc[d, "cleaned_text"][:2000])
                 for d in need]
        for d, s in zip(need, reranker.predict(pairs, batch_size=8)):
            ce[d] = float(s)
            con.execute("insert or replace into ce_scores values (?, ?, ?)", (ticker, int(d), float(s)))
        con.commit()
        del reranker
        free_gpu()
    return ce


def rerank(hybrid, ce):
    top = hybrid[:config.TOP_N]
    final = {d: config.ALPHA * ce[d] + (1 - config.ALPHA) * (1 - rank / len(top)) for rank, d in enumerate(top)}
    return sorted(top, key=lambda d: -final[d]), final


# ---------- chạy cho một công ty ----------

def run(con, ticker, short_name, date_from=None, docs=None):
    docs = load_docs(con) if docs is None else docs
    info = docs.set_index("id")
    ids = company_docs(con, ticker, date_from)

    run_bm25 = bm25_ranking(docs, ids)
    run_dense = dense_ranking(con, ids, info["n_company"])
    hybrid = rrf(run_bm25, run_dense)
    ce = cross_encoder_scores(con, ticker, short_name, hybrid[:config.TOP_N], info)
    ranked, final = rerank(hybrid, ce)

    cfg = json.dumps({"penalty": config.PENALTY, "lam": config.LAM, "rrf_k": config.RRF_K, "w": config.W,
                      "top_n": config.TOP_N, "alpha": config.ALPHA, "er_include_review": config.ER_INCLUDE_REVIEW})
    cur = con.execute("insert into screening_runs (ticker, created_at, date_from, n_mention, n_bm25, n_top, config) "
                      "values (?, ?, ?, ?, ?, ?, ?)",
                      (ticker, db.now(), date_from, len(ids), len(run_bm25), len(ranked), cfg))
    run_id = cur.lastrowid
    bm_rank = {d: i + 1 for i, d in enumerate(run_bm25)}
    de_rank = {d: i + 1 for i, d in enumerate(run_dense)}
    con.executemany("insert into run_results values (?, ?, ?, ?, ?, ?, ?)", [
        (run_id, k + 1, int(d), bm_rank.get(d), de_rank.get(d), ce[d], final[d]) for k, d in enumerate(ranked)
    ])
    con.commit()
    return run_id
