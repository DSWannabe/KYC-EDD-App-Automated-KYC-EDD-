"""Hàm và đường dẫn dùng chung cho các notebook p01-p06."""
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd

# Đường dẫn, có thể ghi đè bằng biến môi trường để chạy thử trên bản sao
DATA = "/home/anhtupham99/kyc/KYC-EDD-App-Automated-KYC-EDD-/Data"
CORPUS_DB = os.environ.get("KYC_CORPUS_DB", f"{DATA}/news_crawler/data/corpus.db")
COMPANY_DB = os.environ.get("KYC_COMPANY_DB", f"{DATA}/kyc_crawler/data/companies.db")
ENV_FILE = os.environ.get("KYC_ENV_FILE", f"{DATA}/news_crawler/.env")

# sqlite3 tự tạo file rỗng khi đường dẫn sai, nên kiểm tra trước để báo lỗi rõ ràng
for _p in [CORPUS_DB, COMPANY_DB]:
    if not Path(_p).is_file():
        raise FileNotFoundError(f"Không thấy file DB: {_p}. Sửa đường dẫn trong common.py.")
BENCH_FILE = os.environ.get("KYC_BENCH_FILE", "/home/anhtupham99/kyc/KYC-EDD-App-Automated-KYC-EDD-/Data/news_crawler/ER_test/benchmark_vn100_can_bang.csv")
OUT_DIR = Path(os.environ.get("KYC_PIPELINE_DIR", "pipeline_data"))
CATALOG = "vn100_20261106"

SEED = 42
TEST_SIZE = 0.3

TU_RE = re.compile(r"\w+|%|/")


# ---------- Văn bản ----------

DOI_DAU = {
    "oà": "òa", "oá": "óa", "oả": "ỏa", "oã": "õa", "oạ": "ọa",
    "oè": "òe", "oé": "óe", "oẻ": "ỏe", "oẽ": "õe", "oẹ": "ọe",
    "uỳ": "ùy", "uý": "úy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy",
}
DOI_DAU.update({k.capitalize(): v.capitalize() for k, v in DOI_DAU.items()})
DOI_DAU_RE = re.compile(r"(?<![qQ])(" + "|".join(DOI_DAU) + r")(?!\w)")


def chuan_hoa(text):
    # NFC, thống nhất vị trí dấu ("hoà" -> "hòa"), gộp khoảng trắng trong dòng
    text = unicodedata.normalize("NFC", str(text or ""))
    text = DOI_DAU_RE.sub(lambda m: DOI_DAU[m.group(1)], text)
    return re.sub(r"[ \t ]+", " ", text).strip()


def tach(s):
    return [x.strip() for x in str(s or "").split(";") if x.strip()]


# ---------- Hồ sơ công ty ----------

def doc_ho_so():
    """Mỗi ticker một dòng: tên đầy đủ, ngành, tên ngắn, lãnh đạo."""
    con = sqlite3.connect(COMPANY_DB)
    catalog = pd.read_sql(f'select ticker, company_name, industry, key_leaders from "{CATALOG}"', con)
    names = pd.read_sql("select * from company_names", con)
    con.close()

    # Lấy các cột tên có trong bảng (mỗi bản DB có thể khác nhau)
    cot_ten = [c for c in ["short_name", "aliases", "strong_aliases", "weak_aliases"] if c in names.columns]
    print("company_names: dùng các cột tên", cot_ten)
    df = catalog.merge(names[["ticker"] + cot_ten], on="ticker", how="left").fillna("")

    def ten_ngan(r):
        # Tên ngắn và alias, bỏ chính mã, bỏ trùng hoa thường
        out = {}
        for x in [t for c in cot_ten for t in tach(r[c])]:
            x = chuan_hoa(x)
            if x and x.upper() != r["ticker"] and x.lower() not in out:
                out[x.lower()] = x
        return list(out.values())

    def lanh_dao(s):
        # "Trần Hùng Huy (CTHĐQT); Từ Tiến Phát (TGĐ)" -> ["Trần Hùng Huy", "Từ Tiến Phát"]
        return [chuan_hoa(re.sub(r"\(.*?\)", "", x)) for x in tach(s)]

    df["ten_ngan"] = df.apply(ten_ngan, axis=1)
    df["lanh_dao"] = df["key_leaders"].map(lanh_dao)
    return df[["ticker", "company_name", "industry", "ten_ngan", "lanh_dao"]].set_index("ticker")


# ---------- Tìm lần nhắc ----------

def tim_ticker(full, ticker):
    # Mã: phân biệt hoa thường, có ranh giới từ
    return [m.span() for m in re.finditer(rf"(?<!\w){re.escape(ticker)}(?!\w)", full)]


def tim_ten(full, ten):
    # Tên: không phân biệt hoa thường, có ranh giới từ
    return [m.span() for m in re.finditer(rf"(?<!\w){re.escape(ten)}(?!\w)", full, re.IGNORECASE)]


def bo_long_nhau(spans):
    # Khoảng nằm trong khoảng dài hơn thì bỏ: "VNDirect" trong "Chứng khoán VNDirect"
    spans = sorted(set(spans), key=lambda x: (x[0], -(x[1] - x[0])))
    out = []
    for s, e in spans:
        if not any(s0 <= s and e <= e0 for s0, e0 in out):
            out.append((s, e))
    return out


def lan_nhac(full, ticker, ten_ngan):
    """Trả về (spans ticker, spans tên ngắn, spans gộp đã bỏ lồng nhau)."""
    sp_ticker = tim_ticker(full, ticker)
    sp_ten = [sp for ten in ten_ngan for sp in tim_ten(full, ten)]
    return sp_ticker, sp_ten, bo_long_nhau(sp_ticker + sp_ten)


# ---------- Cắt đoạn ----------

def doan_van(full, start, end, so_tu=10):
    """Đoạn giữ nguyên chữ hoa, so_tu từ mỗi bên, lần nhắc đặt trong [[ ]] (cho LLM)."""
    trai = full[:start].split()[-so_tu:]
    phai = full[end:].split()[:so_tu]
    return " ".join(trai + [f"[[{full[start:end]}]]"] + phai)


def tu_ngu_canh(full, start, end, so_tu=5):
    """Từ viết thường quanh lần nhắc, gắn tiền tố L_/R_ (cho TF-IDF)."""
    trai = TU_RE.findall(full[max(0, start - 150): start].lower())[-so_tu:]
    phai = TU_RE.findall(full[end: end + 150].lower())[:so_tu]
    return " ".join(["L_" + w for w in trai] + ["R_" + w for w in phai])
