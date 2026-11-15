"""Tìm công ty từ đầu vào: mã chứng khoán, mã số thuế hoặc tên."""
import re

import pandas as pd

import config
from er_resources import LOAI_HINH, goc_mst, read_table, tach
from text import bo_dau

LOAI_HINH_KHONG_DAU = sorted({bo_dau(x) for x in LOAI_HINH} | {"ngan hang tmcp", "ngan hang", "jsc", "corp", "group"},
                             key=len, reverse=True)


def clean_name(name):
    t = bo_dau(name)
    t = re.sub(r"[^\w\s]", " ", t)
    for lh in LOAI_HINH_KHONG_DAU:
        t = re.sub(rf"(?<!\w){lh}(?!\w)", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def load_directory(con_companies):
    catalog = read_table(con_companies, config.CATALOG_TABLE)
    names = read_table(con_companies, "company_names").set_index("ticker")
    rows = []
    for _, c in catalog.iterrows():
        t = c["ticker"]
        n = names.loc[t] if t in names.index else {}
        msts = {goc_mst(c["tax_id"]), goc_mst(n.get("tax_code", "")), *[goc_mst(m) for m in tach(n.get("ma_phu", ""))]}
        ten = {c["company_name"], c["short_name"], n.get("full_name", ""), n.get("short_name", ""),
               *tach(n.get("aliases", "")), *tach(n.get("strong_aliases", ""))}
        rows.append({"ticker": t, "company_name": c["company_name"],
                     "msts": {m for m in msts if m},
                     "names": {clean_name(x) for x in ten if x and clean_name(x)}})
    return rows


def resolve(query, con_companies):
    """Trả về danh sách (ticker, company_name, cách khớp), tốt nhất trước."""
    q = str(query).strip()
    directory = load_directory(con_companies)

    digits = re.sub(r"\D", "", q)
    if len(digits) >= 10 and len(digits) >= len(q.replace(" ", "")) - 2:
        hits = [d for d in directory if goc_mst(digits) in d["msts"]]
        return [(d["ticker"], d["company_name"], "mã số thuế") for d in hits]

    hits = [d for d in directory if d["ticker"] == q.upper()]
    if hits:
        return [(d["ticker"], d["company_name"], "mã chứng khoán") for d in hits]

    cq = clean_name(q)
    if not cq:
        return []
    exact = [d for d in directory if cq in d["names"]]
    if exact:
        return [(d["ticker"], d["company_name"], "tên") for d in exact]

    partial = []
    for d in directory:
        if any(re.search(rf"(?<!\w){re.escape(cq)}(?!\w)", n) for n in d["names"]):
            partial.append((d["ticker"], d["company_name"], "một phần tên"))
    return partial


def profile(con_companies, ticker):
    catalog = read_table(con_companies, config.CATALOG_TABLE).set_index("ticker")
    return catalog.loc[ticker].to_dict() if ticker in catalog.index else {}


def company_row(con_companies, ticker):
    names = pd.read_sql("select * from company_names where ticker = ?", con_companies, params=(ticker,))
    return names.fillna("").replace("NULL", "").iloc[0]
