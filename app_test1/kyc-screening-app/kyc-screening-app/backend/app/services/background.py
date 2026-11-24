"""Việc nền cho bài mới: quét công ty, gắn nhãn ER (mô hình, rồi LLM xem lại cặp chưa chắc), tính vector cho bài ER đã xác nhận.

Chỉ mục BM25 không cần làm mới ở đây: server tự dựng lại ở lần screening kế tiếp khi kho hoặc kết quả ER đổi.
"""
from app.db import connection as db
from app.services.er import ket_qua
from app.services.retrieval import prepare


def chay_nen(bao_cao=print):
    """Trả về dict số lượng đã xử lý ở mỗi bước. Chạy lại nhiều lần không sao."""
    con = db.corpus()
    db.init_schema(con)
    con_cong_ty = db.company()
    try:
        kq = ket_qua.cap_nhat(con, con_cong_ty, bao_cao=bao_cao)
        bao_cao("Tính vector bài mới")
        n_vec = prepare.tinh_vector_bai_moi(con, list(ket_qua.so_cong_ty_cua_bai(con)), bao_cao=bao_cao)
        return {**kq, "bai_tinh_vector": n_vec}
    finally:
        con.close()
        con_cong_ty.close()
