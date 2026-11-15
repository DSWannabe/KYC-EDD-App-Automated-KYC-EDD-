"""LLM đọc các bài đầu bảng xếp hạng, xác nhận rủi ro có thuộc về công ty không (port từ prod_03).

Đọc theo đợt: đọc READ_FIRST bài đầu; nếu 5 bài cuối của đợt vừa đọc có từ EXTEND_IF bài rủi ro trở lên
thì đọc thêm READ_STEP bài, tối đa READ_MAX.
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import config
import db
import llm
from prompts import read_prompt
from text import pick_text, squash


def company_line(ticker, row):
    return f"{ticker} - {row['full_name']} (tên gọi: {row['aliases'] or row['short_name']})"


def company_keys(ticker, row):
    keys = {ticker, row["short_name"], *str(row["aliases"]).split(";")}
    return [k.strip() for k in keys if len(str(k).strip()) >= 3]


def quote_found(quote, title, body):
    q = squash(quote).strip('"“”.… ')
    return int(len(q) > 0 and q in squash(f"{title} {body}"))


def ranked_articles(con, run_id):
    df = pd.read_sql("""
        select r.rank, r.article_id, a.title, a.cleaned_text
        from run_results r join articles a on a.id = r.article_id
        where r.run_id = ? order by r.rank
    """, con, params=(run_id,))
    return df.fillna("")


def read_batch(con, ticker, row, batch):
    done = {d for (d,) in con.execute("select article_id from llm_reads where ticker = ? and prompt_version = ?",
                                      (ticker, config.PROMPT_VERSION))}
    need = batch[~batch.article_id.isin(done)]
    keys = company_keys(ticker, row)

    def ask(r):
        text = pick_text(r.cleaned_text, keys, config.MAX_CHARS, config.HEAD_CHARS)
        return llm.ask_json(read_prompt(ticker, company_line(ticker, row), r.title, text))

    errors = []
    with ThreadPoolExecutor(max_workers=config.WORKERS) as pool:
        futures = {pool.submit(ask, r): r for r in need.itertuples()}
        for f in as_completed(futures):
            r = futures[f]
            try:
                ans = f.result()
            except Exception as e:
                errors.append(f"{r.article_id}: {type(e).__name__}: {str(e)[:150]}")
                continue
            khop = quote_found(ans.get("bang_chung", ""), r.title, r.cleaned_text) if ans.get("lien_quan") else None
            con.execute("insert or replace into llm_reads values (?, ?, ?, ?, ?, ?, ?, ?)",
                        (ticker, int(r.article_id), config.PROMPT_VERSION, config.LLM_MODEL,
                         int(bool(ans.get("lien_quan"))), json.dumps(ans, ensure_ascii=False), khop, db.now()))
    con.commit()
    return errors


def risk_flags(con, ticker, article_ids):
    rows = dict(con.execute(f"""
        select article_id, lien_quan from llm_reads
        where ticker = ? and prompt_version = ? and article_id in ({db.placeholders(article_ids)})
    """, [ticker, config.PROMPT_VERSION, *article_ids]).fetchall())
    return [rows.get(d) for d in article_ids]


def run(con, run_id, ticker, row):
    ranked = ranked_articles(con, run_id)
    depth = min(config.READ_FIRST, len(ranked))
    errors = read_batch(con, ticker, row, ranked.iloc[:depth])

    while depth < min(config.READ_MAX, len(ranked)):
        last5 = risk_flags(con, ticker, [int(d) for d in ranked.article_id.iloc[depth - 5:depth]])
        if sum(1 for x in last5 if x == 1) < config.EXTEND_IF:
            break
        new_depth = min(depth + config.READ_STEP, config.READ_MAX, len(ranked))
        errors += read_batch(con, ticker, row, ranked.iloc[depth:new_depth])
        depth = new_depth

    ids = [int(d) for d in ranked.article_id.iloc[:depth]]
    reads = pd.read_sql(f"""
        select article_id, lien_quan, trich_dan_khop from llm_reads
        where ticker = ? and prompt_version = ? and article_id in ({db.placeholders(ids)})
    """, con, params=[ticker, config.PROMPT_VERSION, *ids]) if ids else pd.DataFrame(
        columns=["article_id", "lien_quan", "trich_dan_khop"])
    risk = reads[reads.lien_quan == 1]
    ty_le_khop = float(risk.trich_dan_khop.mean()) if len(risk) else None
    con.execute("insert or replace into run_llm values (?, ?, ?, ?, ?, ?)",
                (run_id, len(reads), len(risk), len(errors), ty_le_khop, db.now()))
    con.commit()
    return {"depth": depth, "n_read": len(reads), "n_risk": len(risk), "n_error": len(errors),
            "errors": errors, "ty_le_khop": ty_le_khop}
