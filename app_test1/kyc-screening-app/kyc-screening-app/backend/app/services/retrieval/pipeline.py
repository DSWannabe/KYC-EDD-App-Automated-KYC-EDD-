"""Truy xuất bằng chứng cho một công ty (tương đương p02 của kyc_v3).

BM25 -> Dense -> RRF -> cross-encoder rerank. Tham số đọc từ models/cau_hinh.json.
Chỉ mục BM25 dựng một lần trên toàn kho rồi dùng lại; dựng lại khi kho bài hoặc kết quả ER thay đổi.
Danh sách bài của công ty do ER đưa vào (er/ket_qua.py), retrieval không đọc bảng của ER.
"""
import json
import math
import threading
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app import config
from app.services.common import ham_chung as hc
from app.services.retrieval.encoders import lay_encoder, lay_reranker


class Retriever:
    def __init__(self):
        self.cau_hinh = hc.doc_cau_hinh(config.CAU_HINH_FILE)
        self.khoa = threading.Lock()
        self.so_bai_da_nap = -1
        self.info = None          # bảng bài, chỉ mục là id
        self.diem_bm25 = {}       # {id bài: điểm BM25 đã phạt}
        self.vec_truy_van = None  # vector 5 câu mô tả rủi ro

    # ---------- Nạp dữ liệu ----------

    def _nap(self, con, so_cong_ty, bao_cao):
        """Dựng chỉ mục BM25 trên toàn kho (khoảng nửa phút với kho đầy đủ). Bỏ qua nếu kho và kết quả ER không đổi.

        so_cong_ty: {id bài: số công ty ER xác nhận}, dùng để phạt bài nhắc nhiều công ty.
        """
        khoa = (con.execute("select count(*) from articles").fetchone()[0], sum(so_cong_ty.values()))
        if khoa == self.so_bai_da_nap:
            return
        bao_cao(f"Dựng chỉ mục BM25 trên {khoa[0]} bài")

        bai = pd.read_sql("select id, title, cleaned_text, published_at, source_url from articles", con)
        bai["title"] = bai["title"].fillna("")
        bai["cleaned_text"] = bai["cleaned_text"].fillna("")
        bai["noi_dung"] = [hc.lam_sach_noi_dung(t, x) for t, x in zip(bai["title"], bai["cleaned_text"])]
        # bài không có công ty nào được xác nhận: coi như 1, không bị phạt
        bai["n_company"] = [max(so_cong_ty.get(d, 1), 1) for d in bai["id"]]

        tu_cua_bai = [hc.tach_tu_bigram(hc.van_ban_bm25(t, x)) for t, x in zip(bai["title"], bai["noi_dung"])]
        bm25 = hc.BM25(tu_cua_bai)
        diem_goc = bm25.score(hc.cum_tu_thanh_token(hc.CUM_TU_RUI_RO))
        penalty = self.cau_hinh["bm25_penalty"]

        self.diem_bm25 = dict(zip(bai["id"], diem_goc / bai["n_company"].values ** penalty))
        self.info = bai.drop(columns=["cleaned_text"]).set_index("id")
        self.so_bai_da_nap = khoa

    def _nap_truy_van_dense(self):
        if self.vec_truy_van is None:
            self.vec_truy_van = lay_encoder().encode(hc.CAU_TRUY_VAN_RUI_RO).astype(np.float32)

    # ---------- Các bước xếp hạng ----------

    def _xep_bm25(self, ds_bai):
        ds = [d for d in ds_bai if self.diem_bm25[d] > 0]   # bài không có từ rủi ro nào bị bỏ
        return sorted(ds, key=lambda d: -self.diem_bm25[d])

    def _xep_dense(self, con, ds_bai):
        if not ds_bai:
            return []
        dau_hoi = ",".join("?" * len(ds_bai))
        rows = con.execute(f"select article_id, vec from chunk_vectors_v3 where article_id in ({dau_hoi})",
                           list(ds_bai)).fetchall()
        if not rows:
            return []

        vec = np.stack([np.frombuffer(v, dtype=np.float16).astype(np.float32) for _, v in rows])
        diem_doan = (vec @ self.vec_truy_van.T).max(axis=1)   # điểm mỗi đoạn

        diem_bai = {}
        for (d, _), s in zip(rows, diem_doan):
            diem_bai[d] = max(diem_bai.get(d, -1.0), float(s))   # điểm bài = đoạn cao nhất

        lam = self.cau_hinh["dense_lam"]
        diem = {d: s - lam * math.log(self.info.loc[d, "n_company"]) for d, s in diem_bai.items()}
        return sorted(diem, key=lambda d: -diem[d])

    def _gop_rrf(self, runs_bm25, runs_dense):
        k, w = self.cau_hinh["rrf_k"], self.cau_hinh["hybrid_w"]
        tong = defaultdict(float)
        for hang, d in enumerate(runs_bm25):
            tong[d] += 1 / (k + hang + 1)
        for hang, d in enumerate(runs_dense):
            tong[d] += w / (k + hang + 1)
        return sorted(tong, key=lambda d: -tong[d])

    def _cham_ce(self, con, ticker, ten_ngan, top, bao_cao):
        """Điểm cross-encoder của top bài. Cặp đã chấm thì đọc lại từ ce_scores_v3."""
        diem_ce = {d: s for d, s in con.execute("select article_id, score from ce_scores_v3 where ticker = ?", (ticker,))}
        can_cham = [d for d in top if d not in diem_ce]
        if can_cham:
            bao_cao(f"Cross-encoder chấm {len(can_cham)} bài")
            truy_van = hc.cau_truy_van_rerank(ten_ngan)
            cap_van_ban = [(truy_van, hc.van_ban_rerank(self.info.loc[d, "title"], self.info.loc[d, "noi_dung"]))
                           for d in can_cham]
            for d, s in zip(can_cham, lay_reranker().predict(cap_van_ban)):
                diem_ce[d] = float(s)
                con.execute("insert or replace into ce_scores_v3 values (?, ?, ?)", (ticker, int(d), float(s)))
            con.commit()
        return diem_ce

    # ---------- Chạy cho một công ty ----------

    def truy_xuat(self, con, con_cong_ty, ticker, ds_bai, so_cong_ty, date_from=None, bao_cao=print):
        """Trả về run_id (đã lưu vào screening_runs và run_results).

        ds_bai: id các bài ER đã xác nhận nói về ticker (er/ket_qua.bai_cua_cong_ty, đã lọc ngày).
        so_cong_ty: er/ket_qua.so_cong_ty_cua_bai. Retrieval không tự đọc bảng của ER.
        date_from chỉ để ghi vào screening_runs.
        """
        with self.khoa:   # một lần chạy một lúc, tránh dựng chỉ mục hai lần
            self._nap(con, so_cong_ty, bao_cao)
            self._nap_truy_van_dense()
            ds_bai = set(ds_bai)

            bao_cao(f"BM25 và Dense trên {len(ds_bai)} bài có nhắc {ticker}")
            runs_bm25 = self._xep_bm25(ds_bai)
            runs_dense = self._xep_dense(con, ds_bai)
            runs_hybrid = self._gop_rrf(runs_bm25, runs_dense)

            top_n, alpha = self.cau_hinh["rerank_top_n"], self.cau_hinh["rerank_alpha"]
            top = runs_hybrid[:top_n]
            ten_ngan = con_cong_ty.execute("select short_name from company_names where ticker = ?", (ticker,)).fetchone()[0]
            diem_ce = self._cham_ce(con, ticker, ten_ngan, top, bao_cao)

            diem_cuoi = {}
            for hang, d in enumerate(top):
                diem_hang = 1 - hang / len(top)
                diem_cuoi[d] = alpha * diem_ce[d] + (1 - alpha) * diem_hang
            xep_hang = sorted(top, key=lambda d: -diem_cuoi[d])

            return self._luu(con, ticker, date_from, len(ds_bai), runs_bm25, runs_dense, xep_hang, diem_ce, diem_cuoi)

    def _luu(self, con, ticker, date_from, n_mention, runs_bm25, runs_dense, xep_hang, diem_ce, diem_cuoi):
        c = self.cau_hinh
        config_json = json.dumps({"phien_ban": "v3", "penalty": c["bm25_penalty"], "lam": c["dense_lam"],
                                  "rrf_k": c["rrf_k"], "w": c["hybrid_w"], "top_n": c["rerank_top_n"],
                                  "alpha": c["rerank_alpha"]})
        bay_gio = datetime.now(timezone.utc).isoformat()
        cur = con.execute(
            "insert into screening_runs (ticker, created_at, date_from, n_mention, n_bm25, n_top, config) "
            "values (?, ?, ?, ?, ?, ?, ?)",
            (ticker, bay_gio, date_from, n_mention, len(runs_bm25), len(xep_hang), config_json))
        run_id = cur.lastrowid

        hang_bm25 = {d: i + 1 for i, d in enumerate(runs_bm25)}
        hang_dense = {d: i + 1 for i, d in enumerate(runs_dense)}
        for k, d in enumerate(xep_hang):
            con.execute("insert into run_results values (?, ?, ?, ?, ?, ?, ?)",
                        (run_id, k + 1, int(d), hang_bm25.get(d), hang_dense.get(d), diem_ce[d], diem_cuoi[d]))
        con.commit()
        return run_id


_retriever = None
_khoa_tao = threading.Lock()


def lay_retriever():
    """Một Retriever dùng chung cho cả ứng dụng."""
    global _retriever
    with _khoa_tao:
        if _retriever is None:
            _retriever = Retriever()
        return _retriever
