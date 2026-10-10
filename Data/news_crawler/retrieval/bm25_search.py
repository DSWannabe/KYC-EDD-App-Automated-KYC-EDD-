"""
Thu nghiem BM25 tren corpus da thu thap trong news.db.
Tokenize don gian (tach theo khoang trang) - chi de TEST nhanh xem
luong hoat dong; ket qua thi nghiem that can tokenizer tieng Viet
dung nghia (vd underthesea) vi tach theo khoang trang se gop nham
cac tu ghep tieng Viet thanh nhieu token rieng le.
"""

import sqlite3
from pathlib import Path
from rank_bm25 import BM25Okapi
import re
import unicodedata

DB_PATH = Path(__file__).parent.parent / "data" / "corpus.db"


def load_corpus() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, source_url, cleaned_text FROM articles").fetchall()
    conn.close()

    return [{"id": r[0], "source_url": r[1], "text": r[2]} for r in rows if r[2]]


def build_index(corpus: list[dict]) -> BM25Okapi:
    tokenized = [doc["text"].lower().split() for doc in corpus]
    return BM25Okapi(tokenized)


def search(query: str, corpus: list[dict], index: BM25Okapi, top_k: int = 5) -> list[dict]:
    tokenized_query = query.lower().split()
    scores = index.get_scores(tokenized_query)

    ranked = sorted(zip(scores, corpus), key=lambda x: x[0], reverse=True)
    return [
        {"score": round(score, 3), "source_url": doc["source_url"], "text": doc["text"][:200]}
        for score, doc in ranked[:top_k]
    ]

def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).lower()
    syllables = re.findall(r"\w+", text)
    bigrams = [f"{a}_{b}" for a, b in zip(syllables, syllables[1:])]
    return syllables + bigrams

def diagnose(corpus, index, query, must_contain):
    """must_contain: chuoi bat buoc phai co trong bai, vd 'vingroup'."""
    scores = index.get_scores(tokenize(query))
    order = sorted(range(len(corpus)), key=lambda i: scores[i], reverse=True)
    rank_of = {doc_idx: r + 1 for r, doc_idx in enumerate(order)}

    hits = [i for i, d in enumerate(corpus) if must_contain in d["text"].lower()]
    print(f"So bai chua '{must_contain}': {len(hits)} / {len(corpus)}")
    for i in sorted(hits, key=lambda i: rank_of[i])[:10]:
        print(f"  hang {rank_of[i]:>5}  score {scores[i]:.2f}  {corpus[i]['source_url']}")

if __name__ == "__main__":
    query = "Vingroup bị xử phạt hành chính"

    corpus = load_corpus()
    print(f"Corpus co {len(corpus)} bai")

    if not corpus:
        print("Chua co du lieu - chay: python -m jobs.crawl_daily")
    else:
        index = build_index(corpus)
        so_bai = diagnose(corpus, index, query="Vingroup bị xử phạt hành chính", must_contain="vingroup")
        results = search(query, corpus, index)
        print(f"\nTop ket qua cho query '{query}':\n")
        for r in results:
            print(f"[{r['score']}] {r['source_url']}")
            print(f"  {r['text']}...\n")