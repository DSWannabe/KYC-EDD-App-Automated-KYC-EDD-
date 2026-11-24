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


def test_chay_nen_gan_nhan_va_chay_lai(kho_tam):
    from app.db import connection as db
    from app.services.background import chay_nen

    con = db.corpus()
    db.init_schema(con)
    con.execute("delete from er_labels")          # DB mẫu có thể đã có nhãn từ lần chạy trước: bắt đầu từ trạng thái chưa gắn nhãn
    con.commit()
    con.close()

    kq = chay_nen(bao_cao=lambda s: None)
    con = db.corpus()
    n_cap = con.execute("select count(*) from article_company_v3").fetchone()[0]
    n_nhan = con.execute("select count(*) from er_labels").fetchone()[0]
    sai = con.execute("select count(*) from er_labels where label != (score >= ?)", (0.55,)).fetchone()[0]
    xem = con.execute("select ticker, score, label from er_labels order by score desc limit 3").fetchall()
    con.close()
    assert n_cap > 0 and n_nhan == n_cap == kq["cap_gan_nhan"] and sai == 0
    print("ví dụ:", [tuple(r) for r in xem])

    kq2 = chay_nen(bao_cao=lambda s: None)           # chạy lại: không có gì mới
    assert kq2 == {"bai_quet": 0, "bai_tinh_vector": 0, "cap_gan_nhan": 0, "cap_llm_xem_lai": 0}
