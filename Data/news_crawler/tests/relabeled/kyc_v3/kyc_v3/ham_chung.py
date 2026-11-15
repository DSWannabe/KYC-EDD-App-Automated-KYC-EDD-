"""
Các hàm dùng chung cho bộ notebook benchmark (b01 - b07) và production (p00 - p04).

Để chung một chỗ để hai bên xử lý dữ liệu giống hệt nhau:
cấu hình nào đã đánh giá ở benchmark thì production chạy đúng như vậy.

Các mục trong file:
1. Làm sạch nội dung bài
2. Nhận diện công ty trong bài
3. BM25
4. Dense retrieval
5. Rerank bằng cross-encoder
6. LLM đọc bài
7. Đánh giá xếp hạng
"""

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import pandas as pd


# =====================================================================
# 1. Làm sạch nội dung bài
# =====================================================================

def chuan_hoa(text):
    """Đưa chuỗi về dạng Unicode NFC.

    Cùng một chữ tiếng Việt có dấu có thể được lưu bằng hai cách mã khác nhau.
    NFC đưa tất cả về một cách, để so sánh và tìm kiếm không bị trượt.
    Giá trị rỗng (None, NaN) trả về chuỗi rỗng.
    """
    if text is None:
        return ""
    if isinstance(text, float) and math.isnan(text):
        return ""
    return unicodedata.normalize("NFC", str(text))


def gon_khoang_trang(text):
    """Gộp nhiều khoảng trắng liên tiếp thành một và bỏ khoảng trắng ở hai đầu."""
    return " ".join(text.split())


def lam_sach_noi_dung(title, text):
    """Trả về nội dung bài sau khi bỏ dòng tiêu đề bị lặp.

    Trong cleaned_text, dòng đầu tiên thường chính là tiêu đề bài.
    Nếu dòng đầu giống tiêu đề thì bỏ dòng đó.
    Nhờ vậy khi ghép "tiêu đề + nội dung", tiêu đề chỉ xuất hiện một lần.
    """
    title = chuan_hoa(title)
    text = chuan_hoa(text).strip()

    lines = text.split("\n")
    if len(lines) > 0 and gon_khoang_trang(lines[0]) == gon_khoang_trang(title):
        lines = lines[1:]

    return "\n".join(lines).strip()


# =====================================================================
# 2. Nhận diện công ty trong bài
# =====================================================================

def tao_mau_cong_ty(bang_ten):
    """Tạo một biểu thức regex cho mỗi công ty.

    bang_ten là bảng có hai cột: ticker và aliases (các tên gọi, cách nhau bằng dấu ;).
    Cách khớp giống hệt lúc chọn bài để gắn nhãn:
    - tên gọi gồm các aliases và chính mã chứng khoán
    - khớp nguyên từ, có phân biệt chữ hoa chữ thường
    - tên dài được thử trước tên ngắn
    - riêng HCM (Chứng khoán HSC): chỉ khớp các cách gọi của HSC, và chữ "HCM"
      chỉ khớp khi đứng sau "mã", "cổ phiếu", "CP". Như vậy "TP.HCM" không bị tính.

    Trả về dict: {ticker: regex}
    """
    mau = {}
    for ticker, aliases in zip(bang_ten["ticker"], bang_ten["aliases"]):
        ten_goi = set(str(aliases).split(";"))
        ten_goi.add(ticker)

        if ticker == "HCM":
            ten_goi = {"HSC", "Chứng khoán HSC", "Chứng khoán TP.HCM", "Chứng khoán Thành phố Hồ Chí Minh"}

        # bỏ tên rỗng, chuẩn hóa, xếp tên dài lên trước
        ten_goi = [chuan_hoa(t).strip() for t in ten_goi if t.strip() != ""]
        ten_goi = sorted(set(ten_goi), key=len, reverse=True)

        lua_chon = "|".join(re.escape(t) for t in ten_goi)
        if ticker == "HCM":
            lua_chon = lua_chon + r"|(?<=mã )HCM|(?<=cổ phiếu )HCM|(?<=CP )HCM"

        # (?<!\w) và (?!\w): trước và sau tên gọi không được là chữ hoặc số
        mau[ticker] = re.compile(r"(?<!\w)(" + lua_chon + r")(?!\w)")
    return mau


def tim_cong_ty(title, body, mau):
    """Đếm số lần mỗi công ty được nhắc trong tiêu đề và nội dung.

    Trả về dict: {ticker: số lần nhắc}. Công ty không được nhắc thì không có trong dict.
    """
    text = chuan_hoa(title) + "\n" + chuan_hoa(body)
    ket_qua = {}
    for ticker, regex in mau.items():
        so_lan = len(regex.findall(text))
        if so_lan > 0:
            ket_qua[ticker] = so_lan
    return ket_qua


# =====================================================================
# 3. BM25
# =====================================================================

def tach_tu(text):
    """Tách văn bản thành danh sách từ: chuẩn hóa, viết thường, chỉ giữ chữ và số."""
    text = chuan_hoa(text).lower()
    return re.findall(r"\w+", text)


def tach_tu_bigram(text):
    """Danh sách từ đơn cộng với các cặp hai từ liền nhau (bigram).

    Ví dụ "bị khởi tố" -> ["bị", "khởi", "tố", "bị_khởi", "khởi_tố"].
    Tiếng Việt có nhiều từ ghép hai âm tiết, bigram giúp bắt được "khởi_tố" như một từ.
    """
    words = tach_tu(text)
    bigrams = []
    for i in range(len(words) - 1):
        bigrams.append(words[i] + "_" + words[i + 1])
    return words + bigrams


def van_ban_bm25(title, body):
    """Văn bản đưa vào BM25: tiêu đề + nội dung đã làm sạch."""
    return chuan_hoa(title) + " " + chuan_hoa(body)


class BM25:
    """BM25 Okapi viết tay.

    Với mỗi từ trong câu truy vấn, điểm của một bài cộng thêm:
        idf(từ) x tf x (k1 + 1) / (tf + k1 x (1 - b + b x độ dài bài / độ dài trung bình))
    - tf: số lần từ xuất hiện trong bài
    - idf: từ càng hiếm trong kho thì càng có giá trị
    - b: mức phạt bài dài, k1: mức bão hòa khi một từ lặp lại nhiều lần
    """

    def __init__(self, docs, k1=1.2, b=0.75):
        # docs: danh sách các bài, mỗi bài là một danh sách từ
        self.k1 = k1
        self.b = b
        self.N = len(docs)
        self.doc_len = np.array([len(d) for d in docs])
        self.avgdl = self.doc_len.mean()

        # chỉ mục ngược: từ -> {vị trí bài: số lần xuất hiện}
        self.index = defaultdict(dict)
        for i, d in enumerate(docs):
            for term, tf in Counter(d).items():
                self.index[term][i] = tf

        # idf của từng từ
        self.idf = {}
        for term, postings in self.index.items():
            n = len(postings)
            self.idf[term] = math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def score(self, query_tokens):
        """Trả về mảng điểm, mỗi phần tử ứng với một bài (đúng thứ tự docs ban đầu)."""
        scores = np.zeros(self.N)
        for term in set(query_tokens):
            if term not in self.index:
                continue
            idf = self.idf[term]
            for i, tf in self.index[term].items():
                norm = 1 - self.b + self.b * self.doc_len[i] / self.avgdl
                scores[i] += idf * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return scores


# Các cụm từ rủi ro dùng làm câu truy vấn BM25 (giữ như bản BM25 v2 trước đây)
CUM_TU_RUI_RO = [
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


def cum_tu_thanh_token(cum_tu):
    """Đổi danh sách cụm từ thành token cùng kiểu với tach_tu_bigram.

    Cụm một từ giữ nguyên ("ceo"), cụm nhiều từ đổi thành bigram ("khởi tố" -> "khởi_tố").
    """
    tokens = []
    for p in cum_tu:
        words = tach_tu(p)
        if len(words) == 1:
            tokens.append(words[0])
        else:
            for i in range(len(words) - 1):
                tokens.append(words[i] + "_" + words[i + 1])
    return tokens


# =====================================================================
# 4. Dense retrieval
# =====================================================================

SO_TU_MOI_DOAN = 200
SO_DOAN_TOI_DA = 10

# 5 câu mô tả rủi ro. Điểm của một đoạn là độ giống cao nhất với một trong 5 câu này.
CAU_TRUY_VAN_RUI_RO = [
    "doanh nghiệp bị khởi tố, điều tra, xử phạt vì vi phạm pháp luật",
    "công ty bị kiện, tranh chấp tại tòa án",
    "doanh nghiệp thua lỗ, lợi nhuận giảm mạnh, nợ xấu, khó khăn tài chính",
    "chủ tịch, tổng giám đốc từ nhiệm, bị miễn nhiệm, thay đổi lãnh đạo",
    "sự cố, bị cướp, bị mạo danh, lừa đảo, tin đồn ảnh hưởng doanh nghiệp",
]


def cat_doan(title, body):
    """Cắt nội dung bài thành các đoạn SO_TU_MOI_DOAN từ, tối đa SO_DOAN_TOI_DA đoạn.

    Mỗi đoạn có tiêu đề ở đầu, để đoạn nào cũng biết bài nói về chuyện gì.
    Bài không có nội dung vẫn có một đoạn (chỉ có tiêu đề).
    """
    title = chuan_hoa(title)
    words = chuan_hoa(body).split()

    doan = []
    for k in range(SO_DOAN_TOI_DA):
        part = words[k * SO_TU_MOI_DOAN:(k + 1) * SO_TU_MOI_DOAN]
        if len(part) == 0 and k > 0:
            break
        doan.append(title + ". " + " ".join(part))
    return doan


# =====================================================================
# 5. Rerank bằng cross-encoder
# =====================================================================

CAU_RUI_RO_RERANK = "gặp rủi ro: vi phạm, bị điều tra, kiện tụng, thua lỗ, lợi nhuận giảm, nợ xấu, thay đổi lãnh đạo, sự cố"
SO_KY_TU_RERANK = 2000


def cau_truy_van_rerank(ten_ngan):
    """Câu truy vấn cho cross-encoder: tên ngắn của công ty + mô tả rủi ro."""
    return chuan_hoa(ten_ngan) + " " + CAU_RUI_RO_RERANK


def van_ban_rerank(title, body):
    """Văn bản bài cho cross-encoder: tiêu đề + SO_KY_TU_RERANK ký tự đầu của nội dung."""
    return chuan_hoa(title) + ". " + chuan_hoa(body)[:SO_KY_TU_RERANK]


# =====================================================================
# 6. LLM đọc bài
# =====================================================================

def doc_quy_uoc(path):
    """Đọc file quy ước .md làm system prompt.

    Bỏ phần thông tin phiên bản ở đầu file (nằm giữa hai dòng ---), vì phần đó
    chỉ dành cho người đọc, không phải hướng dẫn cho LLM.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if text.startswith("---"):
        cuoi = text.find("\n---", 3)
        text = text[cuoi + 4:]
    return text.strip()


def vi_tri_nhac_ten(body, regex):
    """Danh sách vị trí (số thứ tự ký tự) các lần công ty được nhắc trong nội dung."""
    return [m.start() for m in regex.finditer(chuan_hoa(body))]


def cat_bai_cho_llm(body, vi_tri, max_ky_tu=8000, dau_bai=3000):
    """Cắt bài dài cho vừa với LLM.

    - Bài ngắn hơn max_ky_tu: giữ nguyên.
    - Bài dài: giữ dau_bai ký tự đầu, rồi lần lượt thêm đoạn quanh mỗi lần nhắc tên công ty
      (600 ký tự trước, 900 ký tự sau) cho tới khi đủ max_ky_tu.
      Các phần được nối bằng dòng [...] để LLM biết đã lược bớt.
    """
    body = chuan_hoa(body)
    if len(body) <= max_ky_tu:
        return body

    phan = [body[:dau_bai]]
    da_dung = dau_bai
    het_doan_truoc = dau_bai

    for p in sorted(vi_tri):
        if p < het_doan_truoc:
            continue  # vị trí này đã nằm trong phần đã lấy
        start = max(het_doan_truoc, p - 600)
        end = p + 900
        phan.append(body[start:end])
        da_dung += end - start
        het_doan_truoc = end
        if da_dung >= max_ky_tu:
            break

    return "\n[...]\n".join(phan)


def mo_ta_cong_ty(ticker, bang_ten):
    """Một dòng mô tả công ty cho LLM: mã, tên đầy đủ, các tên gọi khác."""
    row = bang_ten.loc[ticker]
    return f"- {ticker}: {row['full_name']} (tên gọi khác: {row['aliases']})"


def tao_cau_hoi(title, noi_dung_da_cat, danh_sach_cong_ty):
    """Nội dung tin nhắn gửi LLM, theo đúng mục "Đầu vào" của quy ước v4."""
    return (
        "Tiêu đề: " + chuan_hoa(title) + "\n\n"
        "Nội dung:\n" + noi_dung_da_cat + "\n\n"
        "Danh sách công ty cần xét:\n" + "\n".join(danh_sach_cong_ty)
    )


def doc_json(text):
    """Lấy đối tượng JSON trong câu trả lời của LLM (từ dấu { đầu tiên tới dấu } cuối cùng).

    Không tìm thấy hoặc JSON hỏng thì báo lỗi, để bài đó không bị lưu và sẽ được gọi lại.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Khong tim thay JSON trong cau tra loi")
    return json.loads(text[start:end + 1])


def lay_ket_qua_cong_ty(tra_loi, ticker):
    """Lấy dòng kết quả của một công ty trong JSON {"ket_qua": [...]} của LLM."""
    for dong in tra_loi.get("ket_qua", []):
        if str(dong.get("ticker", "")).strip().upper() == ticker:
            return dong
    raise ValueError("LLM khong tra ket qua cho " + ticker)


def la_dung(gia_tri):
    """Đổi giá trị rui_ro của LLM thành True/False (LLM có thể trả true, "true", 1...)."""
    if isinstance(gia_tri, str):
        return gia_tri.strip().lower() in ("true", "1", "yes", "co")
    return bool(gia_tri)


def bang_chung_co_trong_bai(cau, title, body):
    """Câu bằng chứng LLM trích có nằm nguyên văn trong bài không.

    Bỏ qua khác biệt về khoảng trắng, hoa thường và dấu ngoặc kép ở hai đầu.
    Câu rỗng tính là không có.
    """
    def gon(s):
        return gon_khoang_trang(chuan_hoa(s)).lower()

    cau = gon(cau).strip('"“”.… ')
    if cau == "":
        return False
    return cau in gon(title + " " + body)


# =====================================================================
# 7. Đánh giá xếp hạng
# =====================================================================

def tinh_chi_so(xep_hang, bai_dung):
    """Tính các chỉ số cho một công ty.

    xep_hang: danh sách id bài theo thứ tự hệ thống xếp
    bai_dung: tập id các bài thật sự có rủi ro (nhãn 1)

    - P@10: tỷ lệ bài đúng trong 10 bài đầu
    - R@10, R@20: tỷ lệ bài đúng tìm được trong 10, 20 bài đầu
    - nDCG@10: như P@10 nhưng bài đúng đứng càng cao càng được nhiều điểm
    - MRR: 1 / hạng của bài đúng đầu tiên
    - MAP: trung bình độ chính xác tại vị trí của từng bài đúng
    """
    hits = [1 if d in bai_dung else 0 for d in xep_hang]
    so_dung = len(bai_dung)

    ket_qua = {}
    ket_qua["P@10"] = sum(hits[:10]) / 10
    ket_qua["R@10"] = sum(hits[:10]) / so_dung
    ket_qua["R@20"] = sum(hits[:20]) / so_dung

    dcg = 0.0
    for i, h in enumerate(hits[:10]):
        dcg += h / math.log2(i + 2)
    idcg = 0.0
    for i in range(min(so_dung, 10)):
        idcg += 1 / math.log2(i + 2)
    ket_qua["nDCG@10"] = dcg / idcg

    hang_dau_tien = None
    for i, h in enumerate(hits):
        if h == 1:
            hang_dau_tien = i + 1
            break
    ket_qua["MRR"] = 0 if hang_dau_tien is None else 1 / hang_dau_tien

    da_gap, tong = 0, 0.0
    for i, h in enumerate(hits):
        if h == 1:
            da_gap += 1
            tong += da_gap / (i + 1)
    ket_qua["MAP"] = tong / so_dung

    return ket_qua


def doc_du_lieu_danh_gia(file_cap, file_chia):
    """Đọc dữ liệu đánh giá do notebook b02 tạo ra.

    Trả về:
    - ung_vien: {ticker: danh sách id bài được xếp hạng} (chỉ các bài đã gắn nhãn, bỏ khong_ro)
    - dung: {ticker: tập id bài nhãn 1}
    - chia: {ticker: "dev" hoặc "test"} (chỉ các mã được đánh giá)
    """
    cap = pd.read_csv(file_cap)
    cap = cap[cap["dung_danh_gia"] == 1]

    bang_chia = pd.read_csv(file_chia)
    bang_chia = bang_chia[bang_chia["split"].isin(["dev", "test"])]
    chia = dict(zip(bang_chia["ticker"], bang_chia["split"]))

    ung_vien, dung = {}, {}
    for ticker in chia:
        cua_ma = cap[cap["ticker"] == ticker]
        ung_vien[ticker] = sorted(cua_ma["article_id"].tolist())
        dung[ticker] = set(cua_ma.loc[cua_ma["rui_ro"] == 1, "article_id"])
    return ung_vien, dung, chia


def danh_gia_tung_ma(runs, dung, chia):
    """Tính chỉ số cho từng mã. runs: {ticker: danh sách id đã xếp hạng}."""
    rows = []
    for ticker in sorted(chia):
        chi_so = tinh_chi_so(runs[ticker], dung[ticker])
        chi_so["ticker"] = ticker
        chi_so["split"] = chia[ticker]
        chi_so["so_bai_dung"] = len(dung[ticker])
        rows.append(chi_so)
    cot = ["ticker", "split", "so_bai_dung", "P@10", "R@10", "R@20", "nDCG@10", "MRR", "MAP"]
    return pd.DataFrame(rows)[cot]


def tong_hop(bang_tung_ma):
    """Trung bình các chỉ số theo dev, test và toàn bộ."""
    cot = ["P@10", "R@10", "R@20", "nDCG@10", "MRR", "MAP"]
    bang = bang_tung_ma.groupby("split")[cot].mean()
    bang.loc["all"] = bang_tung_ma[cot].mean()
    return bang.round(3)


def ghi_cau_hinh(path, khoa, gia_tri):
    """Ghi một tham số đã chọn vào file cấu hình JSON (production đọc lại file này)."""
    try:
        with open(path, encoding="utf-8") as f:
            cau_hinh = json.load(f)
    except FileNotFoundError:
        cau_hinh = {}
    cau_hinh[khoa] = gia_tri
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cau_hinh, f, ensure_ascii=False, indent=2)
    return cau_hinh


def doc_cau_hinh(path):
    """Đọc file cấu hình JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
