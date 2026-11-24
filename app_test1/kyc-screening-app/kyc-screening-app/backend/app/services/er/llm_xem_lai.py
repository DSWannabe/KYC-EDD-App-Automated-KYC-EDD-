"""LLM xem lại các cặp ER mà mô hình LR chưa chắc (nguon = cho_llm trong er_labels).

Giống p03 của pipeline: tiêu đề + tối đa 3 đoạn ±10 từ quanh lần nhắc, hỏi ER_LLM_SO_LAN lần độc lập,
mỗi lần trả nhãn và độ tự tin. Điểm mỗi lần = tu_tin nếu nhãn 1, ngược lại 1 - tu_tin.
llm_diem = trung bình các lần; nhãn cuối = llm_diem >= 0.5.

Mỗi lần hỏi lưu vào llm_labels, nên lỗi giữa chừng thì lần sau chỉ hỏi phần còn thiếu.
Cặp chưa hỏi đủ vẫn giữ nhãn tạm 1 (nguon = cho_llm).
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd

from app import config
from app.services.er import label
from app.services.llm.client import lay_llm
from app.services.lookup import text

SO_TU = 10
MAX_DOAN = 3
WORKERS = 8

QUY_TAC = '''Nhiệm vụ: xác định bài báo có nhắc tới CHÍNH công ty niêm yết dưới đây hay không, dựa vào các đoạn trích.
Lần nhắc được đánh dấu bằng [[ ]].

Gắn 1 nếu ít nhất một đoạn dùng chuỗi trong [[ ]] để chỉ chính công ty này (pháp nhân niêm yết hoặc thương hiệu của nó),
kể cả khi chỉ nhắc thoáng qua, nằm trong danh sách mã cổ phiếu, hay là ngân hàng nơi mở tài khoản trong danh sách ủng hộ.

Gắn 0 nếu trong mọi đoạn, chuỗi đó chỉ:
- một công ty khác có tên chứa chuỗi đó, kể cả công ty con có tên riêng (ví dụ Chứng khoán ACBS không phải ACB)
- tên người, địa danh, đơn vị tiền tệ (VND), hoặc một từ viết tắt khác trùng chữ'''


def doan_van(full, start, end, so_tu=SO_TU):
    """Đoạn giữ nguyên chữ hoa, so_tu từ mỗi bên, lần nhắc đặt trong [[ ]]."""
    trai = full[:start].split()[-so_tu:]
    phai = full[end:].split()[:so_tu]
    return " ".join(trai + [f"[[{full[start:end]}]]"] + phai)


def tao_prompt(tieu_de, full, ticker, h, nganh):
    _, _, sp = text.lan_nhac(full, ticker, h["ten_ngan"])
    cac = "\n".join(f"{i}. {doan_van(full, s, e)}" for i, (s, e) in enumerate(sp[:MAX_DOAN], start=1))
    cong_ty = f"{ticker} - {h['company_name']} (ngành: {nganh}; tên gọi khác: {', '.join(h['ten_ngan']) or 'không'})"
    return f'''{QUY_TAC}

Công ty: {cong_ty}

Tiêu đề bài: {tieu_de}
Các đoạn trích:
{cac}

Trả lời CHỈ bằng JSON: {{"nhan": 0 hoặc 1, "tu_tin": số từ 0 đến 1 (mức chắc chắn về nhãn), "ly_do": "tối đa 20 từ"}}'''


def hoi_mot_lan(prompt):
    """Một lần hỏi độc lập. Trả về (nhãn, tu_tin, lý do)."""
    tra_loi = lay_llm().hoi(prompt, max_tokens=2000)
    khop = re.search(r"\{.*\}", tra_loi, re.S)
    if not khop:
        raise ValueError(f"LLM không trả JSON: {tra_loi[:150]!r}")
    ans = json.loads(khop.group(0))
    return int(ans["nhan"]), min(max(float(ans["tu_tin"]), 0.0), 1.0), str(ans.get("ly_do", ""))


def xem_lai(con, con_cong_ty, bao_cao=None):
    """Hỏi LLM cho tối đa ER_LLM_TOI_DA cặp đang chờ. Trả về số cặp đã có nhãn LLM sau lần chạy này."""
    ten = label.ten_mo_hinh()
    cap = con.execute("""
        select article_id, ticker from er_labels where model = ? and nguon = 'cho_llm'
        order by article_id limit ?
    """, (ten, config.ER_LLM_TOI_DA)).fetchall()
    if not cap:
        return 0

    ho_so = text.doc_ho_so(con_cong_ty)
    nganh = dict(pd.read_sql(f'select ticker, industry from "{config.CATALOG}"', con_cong_ty).values)

    # Các lần hỏi còn thiếu của từng cặp (đã hỏi thì đọc lại từ llm_labels)
    viec = []   # (article_id, ticker, lan, prompt)
    for article_id, ticker in cap:
        da_hoi = {r[0] for r in con.execute(
            "select lan from llm_labels where article_id = ? and ticker = ? and prompt_version = ?",
            (article_id, ticker, config.ER_PROMPT_VERSION))}
        thieu = [lan for lan in range(1, config.ER_LLM_SO_LAN + 1) if lan not in da_hoi]
        if not thieu:
            continue
        tieu_de, noi_dung = con.execute("select title, cleaned_text from articles where id = ?", (article_id,)).fetchone()
        tieu_de = text.chuan_hoa(tieu_de)
        full = tieu_de + "\n" + text.chuan_hoa(noi_dung)
        p = tao_prompt(tieu_de, full, ticker, ho_so.loc[ticker], nganh.get(ticker, ""))
        viec += [(article_id, ticker, lan, p) for lan in thieu]

    if bao_cao:
        bao_cao(f"LLM xem lại {len(cap)} cặp chưa chắc ({len(viec)} lần hỏi)")
    bay_gio = datetime.now(timezone.utc).isoformat()
    loi, loi_dau = 0, None

    # Các luồng chỉ gọi LLM; ghi DB ở luồng chính vì một kết nối SQLite không dùng chung giữa nhiều luồng
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(hoi_mot_lan, v[3]): v for v in viec}
        for fut in as_completed(futures):
            article_id, ticker, lan, _ = futures[fut]
            try:
                nhan, tu_tin, ly_do = fut.result()
            except Exception as e:
                loi += 1
                loi_dau = loi_dau or f"{type(e).__name__}: {str(e)[:150]}"
                continue
            diem = tu_tin if nhan == 1 else 1 - tu_tin
            con.execute("insert or replace into llm_labels values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (int(article_id), ticker, config.ER_PROMPT_VERSION, lan, nhan, tu_tin, round(diem, 4),
                         ly_do, config.LLM_MODEL, bay_gio))
    con.commit()

    # Cặp đã hỏi đủ số lần: lấy trung bình, ghi nhãn cuối
    xong = 0
    for article_id, ticker in cap:
        cac_diem = [r[0] for r in con.execute(
            "select diem from llm_labels where article_id = ? and ticker = ? and prompt_version = ?",
            (article_id, ticker, config.ER_PROMPT_VERSION))]
        if len(cac_diem) < config.ER_LLM_SO_LAN:
            continue
        llm_diem = round(sum(cac_diem) / len(cac_diem), 4)
        con.execute("update er_labels set score = ?, label = ?, nguon = 'llm' where article_id = ? and ticker = ? and model = ?",
                    (llm_diem, int(llm_diem >= 0.5), article_id, ticker, ten))
        xong += 1
    con.commit()

    if loi and bao_cao:
        # Không dừng job: cặp lỗi vẫn giữ nhãn tạm 1, lần chạy sau sẽ hỏi lại
        bao_cao(f"LLM xem lại lỗi {loi} lần hỏi, sẽ thử lại lần sau. Lỗi đầu tiên: {loi_dau}")
    return xong
