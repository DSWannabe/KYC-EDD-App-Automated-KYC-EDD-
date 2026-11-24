import os
import shutil

os.environ.setdefault("KYC_ENCODER_MODE", "mock")
os.environ.setdefault("KYC_LLM_MODE", "mock")

import pytest

from app import config
from app.services.er import label

pytestmark = pytest.mark.skipif(not label.FILE.is_file(), reason="chưa chạy train_er.py")


@pytest.fixture()
def kho_tam(tmp_path, monkeypatch):
    # Chạy trên bản sao DB mẫu để không đụng dữ liệu thật
    for ten in ["corpus.db", "companies.db"]:
        shutil.copy(config.DATA_DIR / ten, tmp_path / ten)
    monkeypatch.setattr(config, "CORPUS_DB", tmp_path / "corpus.db")
    monkeypatch.setattr(config, "COMPANY_DB", tmp_path / "companies.db")
    return tmp_path


def test_chi_tra_bai_nhan_1(kho_tam):
    from app.db import connection as db
    from app.services.er import ket_qua

    con, con_cong_ty = db.corpus(), db.company()
    db.init_schema(con)
    ket_qua.cap_nhat(con, con_cong_ty, bao_cao=lambda s: None)

    # Chọn mã có cả bài nhãn 1 và nhãn 0 để kiểm tra việc lọc
    ticker = con.execute("""
        select ticker from er_labels where model = ? group by ticker
        having sum(label = 1) > 0 and sum(label = 0) > 0 limit 1
    """, (label.ten_mo_hinh(),)).fetchone()[0]
    bai = set(ket_qua.bai_cua_cong_ty(con, ticker))
    nhan_0 = {r[0] for r in con.execute(
        "select article_id from er_labels where ticker = ? and model = ? and label = 0", (ticker, label.ten_mo_hinh()))}
    tat_ca = {r[0] for r in con.execute("select article_id from article_company_v3 where ticker = ?", (ticker,))}

    assert bai and not (bai & nhan_0) and bai < tat_ca

    so_ct = ket_qua.so_cong_ty_cua_bai(con)
    assert all(so_ct[a] >= 1 for a in bai)
    con.close()
    con_cong_ty.close()
