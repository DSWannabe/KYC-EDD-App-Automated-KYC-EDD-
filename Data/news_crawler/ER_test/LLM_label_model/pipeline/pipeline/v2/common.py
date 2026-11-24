"""Hàm và đường dẫn dùng chung cho các notebook p01-p06, t01-t02, q, r."""
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
OUT_DIR = Path(os.environ.get("KYC_PIPELINE_DIR", "/home/anhtupham99/kyc/KYC-EDD-App-Automated-KYC-EDD-/Data/news_crawler/ER_test/LLM_label_model/pipeline/pipeline/v2/pipeline_data"))
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
    catalog = pd.read_sql(f'select ticker, company_name, industry, key_leaders, tax_id from "{CATALOG}"', con)
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

    def goc_mst(s):
        # 10 số gốc của MST, bỏ phần chi nhánh "-001"; MST 9 số thì thêm số 0 đầu
        so = re.sub(r"\D", "", str(s).split("-")[0])
        return so.zfill(10) if len(so) == 9 else so

    df["ten_ngan"] = df.apply(ten_ngan, axis=1)
    df["lanh_dao"] = df["key_leaders"].map(lanh_dao)
    df["mst"] = df["tax_id"].map(goc_mst)
    return df[["ticker", "company_name", "industry", "ten_ngan", "lanh_dao", "mst"]].set_index("ticker")


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


# ---------- LLM gắn nhãn ER (p05 và t01 dùng chung, giống bước xem lại trong app) ----------

LLM_MODEL = "claude-haiku-5-5"
PROMPT_VERSION = "v2"        # đổi prompt thì tăng số này
SO_LAN = 5                   # số lần hỏi mỗi cặp, lấy trung bình điểm
LLM_FILE = OUT_DIR / "llm_er.csv"   # mọi lần hỏi đều lưu ở đây, chạy lại không hỏi lại

QUY_TAC = '''Nhiệm vụ: xác định bài báo có nhắc tới CHÍNH công ty niêm yết dưới đây hay không, dựa vào các đoạn trích.
Lần nhắc được đánh dấu bằng [[ ]].

Gắn 1 nếu ít nhất một đoạn dùng chuỗi trong [[ ]] để chỉ chính công ty này (pháp nhân niêm yết hoặc thương hiệu của nó),
kể cả khi chỉ nhắc thoáng qua, nằm trong danh sách mã cổ phiếu, hay là ngân hàng nơi mở tài khoản trong danh sách ủng hộ.

Gắn 0 nếu trong mọi đoạn, chuỗi đó chỉ:
- một công ty khác có tên chứa chuỗi đó, kể cả công ty con có tên riêng (ví dụ Chứng khoán ACBS không phải ACB)
- tên người, địa danh, đơn vị tiền tệ (VND), hoặc một từ viết tắt khác trùng chữ'''


def tao_prompt(ticker, h, tieu_de, full):
    """Tiêu đề + tối đa 3 đoạn ±10 từ quanh lần nhắc. h: một dòng của doc_ho_so()."""
    _, _, sp = lan_nhac(full, ticker, h["ten_ngan"])
    cac = "\n".join(f"{i}. {doan_van(full, s, e)}" for i, (s, e) in enumerate(sp[:3], start=1))
    cong_ty = f"{ticker} - {h['company_name']} (ngành: {h['industry']}; tên gọi khác: {', '.join(h['ten_ngan']) or 'không'})"
    return f'''{QUY_TAC}

Công ty: {cong_ty}

Tiêu đề bài: {tieu_de}
Các đoạn trích:
{cac}

Trả lời CHỈ bằng JSON: {{"nhan": 0 hoặc 1, "tu_tin": số từ 0 đến 1 (mức chắc chắn về nhãn), "ly_do": "tối đa 20 từ"}}'''


def hoi_mot_lan(client, text, retries=3):
    """Một lần hỏi độc lập (LLM chỉ thấy prompt, không thấy các lần khác). Trả về (nhãn, tự tin, lý do)."""
    import json
    import time
    for lan in range(retries):
        msg = client.messages.create(model=LLM_MODEL, max_tokens=2000, messages=[{"role": "user", "content": text}])
        tra_loi = "".join(b.text for b in msg.content if b.type == "text")
        khop = re.search(r"\{.*\}", tra_loi, re.S)
        try:
            ans = json.loads(khop.group(0))
            return int(ans["nhan"]), min(max(float(ans["tu_tin"]), 0.0), 1.0), str(ans.get("ly_do", ""))
        except Exception:
            if lan == retries - 1:
                raise ValueError(f"stop_reason={msg.stop_reason} | trả lời: {tra_loi[:200]!r}")
            time.sleep(2 ** lan)


def doc_llm():
    """Các lần hỏi đã lưu (đúng PROMPT_VERSION)."""
    if not LLM_FILE.exists():
        return pd.DataFrame(columns=["article_id", "ticker", "prompt_version", "lan", "nhan", "tu_tin", "diem", "ly_do"])
    df = pd.read_csv(LLM_FILE)
    return df[df["prompt_version"] == PROMPT_VERSION]


def chay_llm(cap, bai, ho_so, workers=8, luu_moi=200):
    """Hỏi LLM SO_LAN lần cho mỗi cặp trong cap (cột article_id, ticker), chỉ hỏi các lần còn thiếu.
    Mỗi lần một dòng trong LLM_FILE. Trả về danh sách lỗi."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    import anthropic
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE)
    client = anthropic.Anthropic()
    tieu_de = dict(zip(bai["article_id"], bai["title"]))
    full = dict(zip(bai["article_id"], bai["full"]))

    da_hoi = set(zip(*[doc_llm()[c] for c in ["article_id", "ticker", "lan"]]))
    viec = [(a, t, lan) for a, t in zip(cap["article_id"], cap["ticker"])
            for lan in range(1, SO_LAN + 1) if (a, t, lan) not in da_hoi]
    print("cặp:", len(cap), "| lần hỏi còn thiếu:", len(viec))

    moi, loi = [], []

    def luu():
        cu = pd.read_csv(LLM_FILE) if LLM_FILE.exists() else None
        pd.concat([cu, pd.DataFrame(moi)], ignore_index=True).to_csv(LLM_FILE, index=False)
        moi.clear()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(hoi_mot_lan, client, tao_prompt(t, ho_so.loc[t], tieu_de[a], full[a])): (a, t, lan)
                   for a, t, lan in viec}
        for f in as_completed(futures):
            a, t, lan = futures[f]
            try:
                nhan, tu_tin, ly_do = f.result()
            except Exception as e:
                loi.append(f"{a}/{t}/lần {lan}: {type(e).__name__}: {str(e)[:150]}")
                continue
            moi.append({"article_id": a, "ticker": t, "prompt_version": PROMPT_VERSION, "lan": lan, "nhan": nhan,
                        "tu_tin": tu_tin, "diem": round(tu_tin if nhan == 1 else 1 - tu_tin, 4), "ly_do": ly_do,
                        "model": LLM_MODEL})
            if len(moi) >= luu_moi:
                luu()
    if moi:
        luu()
    print("lỗi:", len(loi))
    for x in loi[:5]:
        print(" ", x)
    return loi


def diem_llm():
    """Mỗi cặp đã hỏi đủ SO_LAN lần: llm_diem (trung bình điểm), llm_nhat_quan (tỷ lệ trả lời 1)."""
    df = doc_llm()
    g = df.groupby(["article_id", "ticker"]).agg(so_lan=("diem", "size"), llm_diem=("diem", "mean"),
                                                 llm_nhat_quan=("nhan", "mean")).reset_index()
    return g[g["so_lan"] >= SO_LAN].drop(columns="so_lan").round(4)


def chuyen_tu_p03_cu():
    """Ghép các lần hỏi trong p03_llm.csv cũ (dạng rộng nhan_1..5, diem_1..5) vào LLM_FILE. Chạy lại không sao."""
    cu = OUT_DIR / "p03_llm.csv"
    if not cu.exists():
        return 0
    p03 = pd.read_csv(cu)
    p03 = p03[p03["prompt_version"] == PROMPT_VERSION]
    dong = []
    for r in p03.itertuples():
        for lan in range(1, SO_LAN + 1):
            nhan, diem = getattr(r, f"nhan_{lan}", None), getattr(r, f"diem_{lan}", None)
            if pd.notna(nhan) and pd.notna(diem):
                tu_tin = diem if nhan == 1 else 1 - diem
                dong.append({"article_id": r.article_id, "ticker": r.ticker, "prompt_version": PROMPT_VERSION,
                             "lan": lan, "nhan": int(nhan), "tu_tin": round(tu_tin, 4), "diem": diem, "ly_do": "",
                             "model": getattr(r, "model", LLM_MODEL)})
    co = pd.read_csv(LLM_FILE) if LLM_FILE.exists() else pd.DataFrame()
    # Lần hỏi đã có trong LLM_FILE thì giữ bản đó
    gop = pd.concat([pd.DataFrame(dong), co]).drop_duplicates(["article_id", "ticker", "prompt_version", "lan"], keep="last")
    gop.to_csv(LLM_FILE, index=False)
    return len(gop) - len(co)
