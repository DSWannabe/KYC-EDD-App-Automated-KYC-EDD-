"""Một lần screening cho một công ty:
cập nhật ER -> tính vector -> truy xuất bằng chứng -> LLM đọc top 20 -> gộp sự kiện, viết báo cáo.

Danh sách bài lấy qua er/ket_qua.py: chỉ bài ER xác nhận đúng là nói về công ty.
"""
from app.db import connection as db
from app.services.er import ket_qua
from app.services.llm import doc_bai
from app.services.report import build
from app.services.retrieval import prepare
from app.services.retrieval.pipeline import lay_retriever


def chay_screening(ticker, cap_nhat, date_from=None):
    """Trả về run_id. `cap_nhat(step=...)` báo bước đang chạy cho StatusBanner."""
    con = db.corpus()
    con_cong_ty = db.company()

    def bao_cao(s):
        cap_nhat(step=s)

    try:
        ket_qua.cap_nhat(con, con_cong_ty, bao_cao=bao_cao)   # bài mới về từ lần chạy nền trước
        so_cong_ty = ket_qua.so_cong_ty_cua_bai(con)
        ds_bai = ket_qua.bai_cua_cong_ty(con, ticker, date_from)
        prepare.tinh_vector_bai_moi(con, ds_bai, bao_cao=bao_cao)

        run_id = lay_retriever().truy_xuat(con, con_cong_ty, ticker, ds_bai, so_cong_ty,
                                           date_from=date_from, bao_cao=bao_cao)

        cap_nhat(step="LLM đọc top bài")
        doc_bai.doc_top(con, con_cong_ty, run_id, ticker, bao_cao=bao_cao)

        build.tao_bao_cao(con, con_cong_ty, run_id, ticker, bao_cao=bao_cao)
        return run_id
    finally:
        con.close()
        con_cong_ty.close()
