"""LLM chỉ xem lại các cặp mà mô hình LR chưa chắc (điểm trong vùng xem lại)."""
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
    for ten in ["corpus.db", "companies.db"]:
        shutil.copy(config.DATA_DIR / ten, tmp_path / ten)
    monkeypatch.setattr(config, "CORPUS_DB", tmp_path / "corpus.db")
    monkeypatch.setattr(config, "COMPANY_DB", tmp_path / "companies.db")
    from app.db import connection as db
    con = db.corpus()
    db.init_schema(con)
    con.execute("delete from er_labels")   # bắt đầu từ trạng thái chưa gắn nhãn
    con.execute("delete from llm_labels")
    con.commit()
    con.close()
    return tmp_path


class LLMHong:
    def hoi(self, user, system=None, max_tokens=2000):
        raise ConnectionError("API không phản hồi")


def _dem(con):
    return dict(con.execute("select nguon, count(*) from er_labels group by nguon").fetchall())


def test_chi_cap_chua_chac_moi_hoi_llm(kho_tam):
    from app.db import connection as db
    from app.services.er import ket_qua

    con, con_cong_ty = db.corpus(), db.company()
    kq = ket_qua.cap_nhat(con, con_cong_ty, bao_cao=lambda s: None)
    thap, cao = label.vung_xem_lai()

    # Cặp LLM xem lại đúng là cặp có điểm LR trong vùng; cặp ngoài vùng giữ nhãn LR
    trong_vung = con.execute("select count(*) from er_labels where score_lr between ? and ?", (thap, cao)).fetchone()[0]
    dem = _dem(con)
    assert dem.get("llm", 0) == trong_vung == kq["cap_llm_xem_lai"] > 0
    assert "cho_llm" not in dem
    assert con.execute("select count(*) from er_labels where nguon = 'lr' and score_lr between ? and ?",
                       (thap, cao)).fetchone()[0] == 0

    # Mỗi cặp xem lại có đủ số lần hỏi; điểm cuối là trung bình các lần
    so_lan = con.execute("select count(*) from llm_labels").fetchone()[0]
    assert so_lan == trong_vung * config.ER_LLM_SO_LAN
    con.close()
    con_cong_ty.close()


def test_llm_loi_thi_giu_nhan_tam_va_hoi_lai(kho_tam, monkeypatch):
    from app.db import connection as db
    from app.services.er import ket_qua
    from app.services.llm import client

    con, con_cong_ty = db.corpus(), db.company()
    monkeypatch.setattr(client, "_llm", LLMHong())
    ket_qua.cap_nhat(con, con_cong_ty, bao_cao=lambda s: None)

    # LLM hỏng: cặp chưa chắc chờ LLM, tạm gắn nhãn 1 để không bỏ sót bài
    dem = _dem(con)
    assert dem.get("cho_llm", 0) > 0 and "llm" not in dem
    assert con.execute("select count(*) from er_labels where nguon = 'cho_llm' and label != 1").fetchone()[0] == 0

    # LLM chạy lại được: lần sau hỏi nốt các cặp đang chờ
    monkeypatch.setattr(client, "_llm", client.MockLLM())
    kq = ket_qua.cap_nhat(con, con_cong_ty, bao_cao=lambda s: None)
    assert kq["cap_gan_nhan"] == 0 and kq["cap_llm_xem_lai"] == dem["cho_llm"]
    assert "cho_llm" not in _dem(con)
    con.close()
    con_cong_ty.close()
