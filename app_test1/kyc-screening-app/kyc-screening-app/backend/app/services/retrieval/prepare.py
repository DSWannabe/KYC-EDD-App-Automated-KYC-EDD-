"""Chuẩn bị cho truy xuất bằng chứng.

- tao_mau: regex tìm tên công ty, dùng khi cắt bài cho LLM đọc (llm/doc_bai.py, report/build.py)
- tinh_vector_bai_moi: cắt đoạn và mã hóa các bài chưa có vector, ghi vào chunk_vectors_v3

Việc quét bài tìm công ty thuộc về ER (er/quet.py), không nằm ở đây.
"""
import numpy as np
import pandas as pd

from app.services.common import ham_chung as hc
from app.services.retrieval.encoders import lay_encoder

SO_BAI_MOI_LAN = 200   # mỗi lần mã hóa 200 bài rồi lưu


def tao_mau(con_cong_ty):
    """Mẫu regex tìm tên của từng công ty, từ bảng company_names."""
    bang_ten = pd.read_sql("select ticker, aliases from company_names", con_cong_ty)
    return hc.tao_mau_cong_ty(bang_ten)


def tinh_vector_bai_moi(con, ds_bai, bao_cao=None):
    """ds_bai: id các bài cần có vector (thường là bài ER đã xác nhận). Trả về số bài vừa tính."""
    da_co = {r[0] for r in con.execute("select distinct article_id from chunk_vectors_v3")}
    can_tinh_id = [int(d) for d in ds_bai if d not in da_co]
    if not can_tinh_id:
        return 0

    dau_hoi = ",".join("?" * len(can_tinh_id))
    can_tinh = con.execute(f"select id, title, cleaned_text from articles where id in ({dau_hoi})",
                           can_tinh_id).fetchall()

    encoder = lay_encoder()
    for start in range(0, len(can_tinh), SO_BAI_MOI_LAN):
        van_ban, khoa = [], []
        for article_id, title, text in can_tinh[start:start + SO_BAI_MOI_LAN]:
            title, text = title or "", text or ""
            noi_dung = hc.lam_sach_noi_dung(title, text)
            for k, doan in enumerate(hc.cat_doan(title, noi_dung)):
                van_ban.append(doan)
                khoa.append((int(article_id), k))

        vec = encoder.encode(van_ban)
        dong = [(a, k, v.astype(np.float16).tobytes()) for (a, k), v in zip(khoa, vec)]
        con.executemany("insert into chunk_vectors_v3 values (?, ?, ?)", dong)
        con.commit()
        if bao_cao:
            bao_cao(f"Tính vector {min(start + SO_BAI_MOI_LAN, len(can_tinh))}/{len(can_tinh)} bài")
    return len(can_tinh)
