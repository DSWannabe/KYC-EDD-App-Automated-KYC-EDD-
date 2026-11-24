"""Hợp đồng giữa ER và phần còn lại của app.

Phần khác (retrieval, screening, báo cáo) chỉ gọi ba hàm ở đây, không đọc thẳng bảng của ER.
Nhờ vậy ER đổi bảng, đổi mô hình hay thêm LLM thì phần khác không phải sửa.
"""
from app.services.er import label, llm_xem_lai, quet
from app.services.lookup import text


def cap_nhat(con, con_cong_ty, bao_cao=print):
    """Quét bài mới, mô hình gắn nhãn cặp mới, LLM xem lại cặp mô hình chưa chắc.
    Chạy lại nhiều lần không sao. Trả về số lượng đã xử lý ở mỗi bước."""
    bao_cao("Quét bài mới")
    n_quet = quet.quet_bai_moi(con, text.doc_ho_so(con_cong_ty))
    bao_cao("Gắn nhãn ER")
    n_nhan = label.gan_nhan_moi(con, con_cong_ty, bao_cao=bao_cao)
    n_llm = llm_xem_lai.xem_lai(con, con_cong_ty, bao_cao=bao_cao)
    return {"bai_quet": n_quet, "cap_gan_nhan": n_nhan, "cap_llm_xem_lai": n_llm}


def bai_cua_cong_ty(con, ticker, date_from=None):
    """Id các bài mà ER xác nhận đúng là nói về ticker (nhãn 1), lọc theo ngày đăng nếu có."""
    rows = con.execute("""
        select e.article_id from er_labels e
        join articles a on a.id = e.article_id
        where e.ticker = ? and e.model = ? and e.label = 1
          and (? is null or a.published_at >= ?)
        order by e.article_id
    """, (ticker, label.ten_mo_hinh(), date_from, date_from)).fetchall()
    return [r[0] for r in rows]


def so_cong_ty_cua_bai(con):
    """{id bài: số công ty ER xác nhận trong bài}. Bài không có công ty nào thì không có trong dict."""
    rows = con.execute("""
        select article_id, count(*) from er_labels
        where model = ? and label = 1
        group by article_id
    """, (label.ten_mo_hinh(),)).fetchall()
    return {r[0]: r[1] for r in rows}
