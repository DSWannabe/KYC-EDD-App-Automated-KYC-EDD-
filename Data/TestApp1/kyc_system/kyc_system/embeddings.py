"""Vector bge-m3 cho các bài có nhắc công ty (giữ định dạng chunk_vectors của prod_01)."""
import numpy as np
import pandas as pd

import config
import db


def make_chunks(title, body):
    words = str(body).split()
    chunks = []
    for k in range(config.MAX_CHUNKS):
        part = words[k * config.CHUNK_WORDS:(k + 1) * config.CHUNK_WORDS]
        if not part and k > 0:
            break
        chunks.append(f"{title}. " + " ".join(part))
    return chunks


def load_encoder():
    from sentence_transformers import SentenceTransformer
    encoder = SentenceTransformer(config.EMBED_MODEL, device=config.DEVICE)
    if config.DEVICE == "cuda":
        encoder.half()
    encoder.max_seq_length = 512
    return encoder


def free_gpu():
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def articles_without_vectors(con):
    # chỉ các bài có ít nhất một cặp được dùng cho truy xuất
    decisions = ("1", "xem") if config.ER_INCLUDE_REVIEW else ("1",)
    return pd.read_sql(f"""
        select a.id, a.title, a.cleaned_text from articles a
        where a.id in (select article_id from er_article_company where quyet_dinh in ({db.placeholders(decisions)}))
          and a.id not in (select distinct article_id from chunk_vectors)
        order by a.id
    """, con, params=list(decisions)).fillna("")


def compute_missing(con):
    todo = articles_without_vectors(con)
    print("Số bài cần tính vector:", len(todo))
    if len(todo) == 0:
        return 0

    encoder = load_encoder()
    for start in range(0, len(todo), config.EMBED_BATCH):
        part = todo.iloc[start:start + config.EMBED_BATCH]
        texts, keys = [], []
        for i, title, body in zip(part["id"], part["title"], part["cleaned_text"]):
            for k, ch in enumerate(make_chunks(title, body)):
                texts.append(ch)
                keys.append((int(i), k))
        vecs = encoder.encode(texts, batch_size=16, normalize_embeddings=True)
        con.executemany("insert or replace into chunk_vectors values (?, ?, ?)",
                        [(i, k, np.asarray(v).astype(np.float16).tobytes()) for (i, k), v in zip(keys, vecs)])
        con.commit()
        print("  vector:", min(start + config.EMBED_BATCH, len(todo)), "/", len(todo))
    del encoder
    free_gpu()
    return len(todo)
