"""LLM đọc từng bài trong top của một lần truy xuất (tương đương p03 của kyc_v3).

Mỗi lần gọi là một cặp (công ty, bài), danh sách công ty chỉ có một mã, system prompt là quy ước v4.
Cặp đã đọc (cùng PROMPT_VERSION) thì không gọi lại.
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd

from app import config
from app.services.common import ham_chung as hc
from app.services.llm.client import lay_llm
from app.services.retrieval import prepare

TOP_K = 20
MAX_CHARS = 8000    # độ dài tối đa của nội dung đưa vào LLM
HEAD_CHARS = 3000   # luôn giữ phần đầu bài
WORKERS = 8         # số yêu cầu gửi cùng lúc, gặp lỗi rate limit thì giảm xuống 4

_system = None


def _lay_system():
    global _system
    if _system is None:
        _system = hc.doc_quy_uoc(config.QUY_UOC_FILE)
    return _system


def doc_top(con, con_cong_ty, run_id, ticker, bao_cao=lambda s: None):
    """LLM đọc top TOP_K của run_id. Trả về số bài LLM kết luận là rủi ro."""
    top = con.execute("select article_id from run_results where run_id = ? and rank <= ? order by rank",
                      (run_id, TOP_K)).fetchall()
    ds_bai = [r[0] for r in top]
    if not ds_bai:
        _luu_tom_tat(con, run_id, ticker, 0)
        return 0

    dau_hoi = ",".join("?" * len(ds_bai))
    bai = {r["id"]: r for r in con.execute(
        f"select id, title, cleaned_text from articles where id in ({dau_hoi})", ds_bai)}
    mau = prepare.tao_mau(con_cong_ty)
    bang_ten = pd.read_sql("select * from company_names", con_cong_ty).set_index("ticker")

    def tao_tin_nhan(d):
        title = bai[d]["title"] or ""
        noi_dung = hc.lam_sach_noi_dung(title, bai[d]["cleaned_text"] or "")
        vi_tri = hc.vi_tri_nhac_ten(noi_dung, mau[ticker])
        noi_dung_cat = hc.cat_bai_cho_llm(noi_dung, vi_tri, MAX_CHARS, HEAD_CHARS)
        return hc.tao_cau_hoi(title, noi_dung_cat, [hc.mo_ta_cong_ty(ticker, bang_ten)]), title, noi_dung

    def hoi_llm(d):
        tin_nhan, title, noi_dung = tao_tin_nhan(d)
        text = lay_llm().hoi(tin_nhan, system=_lay_system(), max_tokens=2000)
        dong = hc.lay_ket_qua_cong_ty(hc.doc_json(text), ticker)
        khop = None
        if hc.la_dung(dong.get("rui_ro")):
            khop = int(hc.bang_chung_co_trong_bai(dong.get("bang_chung", ""), title, noi_dung))
        return dong, khop

    da_co = {r[0] for r in con.execute("select article_id from llm_reads where ticker = ? and prompt_version = ?",
                                       (ticker, config.PROMPT_VERSION))}
    can_goi = [d for d in ds_bai if d not in da_co]
    loi, loi_dau = 0, None
    bay_gio = datetime.now(timezone.utc).isoformat()

    # Các luồng chỉ gọi LLM. Ghi DB ở luồng chính vì một kết nối SQLite không dùng chung giữa nhiều luồng.
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(hoi_llm, d): d for d in can_goi}
        for k, fut in enumerate(as_completed(futures), start=1):
            d = futures[fut]
            try:
                dong, khop = fut.result()
            except Exception as e:
                loi += 1   # không lưu, lần chạy sau sẽ gọi lại
                loi_dau = loi_dau or f"{type(e).__name__}: {str(e)[:150]}"
                continue
            rui_ro = hc.la_dung(dong.get("rui_ro"))
            con.execute("insert or replace into llm_reads values (?, ?, ?, ?, ?, ?, ?, ?)",
                        (ticker, int(d), config.PROMPT_VERSION, config.LLM_MODEL, int(rui_ro),
                         json.dumps(dong, ensure_ascii=False), khop, bay_gio))
            con.commit()
            bao_cao(f"LLM đọc bài {k}/{len(can_goi)}")

    n_rui_ro = _luu_tom_tat(con, run_id, ticker, loi)
    if loi:
        # Không được đi tiếp: bài đọc lỗi mà bị coi là "không rủi ro" thì báo cáo sẽ bỏ sót sự kiện.
        # Các bài đã đọc xong đã được lưu, chạy lại chỉ gọi lại các bài lỗi.
        raise RuntimeError(f"LLM đọc lỗi {loi}/{len(can_goi)} bài. Lỗi đầu tiên: {loi_dau}")
    return n_rui_ro


def _luu_tom_tat(con, run_id, ticker, so_loi):
    """Ghi run_llm: số bài đã đọc, số bài rủi ro, số lỗi, tỷ lệ câu bằng chứng khớp nguyên văn."""
    rows = con.execute("""
        select l.lien_quan, l.trich_dan_khop from run_results r
        join llm_reads l on l.ticker = ? and l.article_id = r.article_id and l.prompt_version = ?
        where r.run_id = ? and r.rank <= ?
    """, (ticker, config.PROMPT_VERSION, run_id, TOP_K)).fetchall()
    rui_ro = [r for r in rows if r[0] == 1]
    khop = [r[1] for r in rui_ro if r[1] is not None]
    ty_le = sum(khop) / len(khop) if khop else None
    con.execute("insert or replace into run_llm values (?, ?, ?, ?, ?, ?)",
                (run_id, len(rows), len(rui_ro), so_loi, ty_le, datetime.now(timezone.utc).isoformat()))
    con.commit()
    return len(rui_ro)
