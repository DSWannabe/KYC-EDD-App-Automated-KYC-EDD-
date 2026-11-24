import os
from pathlib import Path

os.environ.setdefault("KYC_ENCODER_MODE", "mock")
os.environ.setdefault("KYC_LLM_MODE", "mock")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.lookup import model

pytestmark = pytest.mark.skipif(not model.FILE.is_file(), reason="chưa chạy train_lookup.py")
client = TestClient(app)


def goi(doan, ten=None):
    r = client.post("/lookup", json={"doan": doan, "ten": ten})
    assert r.status_code == 200, r.text
    return r.json()["ket_qua"]


def test_ma_viet_hoa_trong_ngu_canh_co_phieu():
    kq = goi("Cổ phiếu ACB tăng 2% trong phiên sáng nay, thanh khoản cải thiện ở nhóm ngân hàng.", "ACB")
    assert kq[0]["trang_thai"] in ("duy_nhat", "can_xac_nhan")
    assert kq[0]["ung_vien"][0]["ticker"] == "ACB"


def test_ten_khong_phai_cong_ty():
    kq = goi("Giá vé máy bay 1.500.000 VND một chiều, tăng mạnh dịp Tết.", "VND")
    assert kq[0]["trang_thai"] in ("khong_co", "can_xac_nhan")


def test_tu_dong_tim_nhieu_ten():
    kq = goi("Cổ phiếu FPT và HPG dẫn dắt thị trường, khối ngoại mua ròng mạnh.")
    ten = {k["ten"] for k in kq}
    assert {"FPT", "HPG"} <= ten


def test_ten_khong_co_trong_doan():
    kq = goi("Thời tiết hôm nay nắng đẹp.", "Vingroup")
    assert kq[0]["trang_thai"] == "khong_co" and kq[0]["ghi_chu"]


def test_doan_trong():
    assert client.post("/lookup", json={"doan": "  "}).status_code == 422


def test_bo_cham_json_chay_duoc():
    # So khớp với sklearn đã kiểm bằng tay trên cặp test (sai số ~1e-16); ở đây chỉ kiểm bộ chấm chạy được
    import json
    d = json.loads(model.FILE.read_text(encoding="utf-8"))
    mh = model.MoHinh()
    dong = {"co_ticker": 1, "co_ten_ngan": 0, "so_lanh_dao": 0, "log_so_nhac": 0.69, "khop_chinh_xac": 1,
            "ngu_canh": "L_cổ L_phiếu R_tăng R_2 R_% L_zzzkhongco"}
    p = mh.diem(dong)
    assert 0 < p < 1 and len(d["idf"]) == len(d["he_so_tu"])
