"""Kiểm tra luồng POST /screening -> GET /screening/{job_id} -> GET /reports/{run_id} trên DB mẫu (encoder và LLM giả).

Chạy trong thư mục backend/:  python -m pytest tests -q
"""
import os
import shutil
import tempfile
import time
from pathlib import Path

# Đặt biến môi trường TRƯỚC khi import app: dùng bản sao DB mẫu để không làm bẩn DB gốc
_goc = Path(os.environ.get("KYC_DATA_DIR", Path(__file__).resolve().parents[2] / "data" / "sample"))
_tam = Path(tempfile.mkdtemp())
for f in ["corpus.db", "companies.db"]:
    shutil.copy2(_goc / f, _tam / f)
os.environ["KYC_DATA_DIR"] = str(_tam)
os.environ["KYC_ENCODER_MODE"] = "mock"
os.environ["KYC_LLM_MODE"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import app  # noqa: E402

# config có thể đã được nạp bởi file test khác (biến môi trường ở trên khi đó không còn tác dụng),
# nên trỏ thẳng đường dẫn DB vào bản sao
config.CORPUS_DB = _tam / "corpus.db"
config.COMPANY_DB = _tam / "companies.db"

from app.main import app  # noqa: E402


def doi_job(client, job_id, toi_da=60):
    bat_dau = time.time()
    while time.time() - bat_dau < toi_da:
        kq = client.get(f"/screening/{job_id}").json()
        if kq["status"] in ("done", "error"):
            return kq
        time.sleep(0.2)
    raise TimeoutError("job chạy quá lâu")


def test_screening_ca_binh_thuong():
    with TestClient(app) as client:
        r = client.post("/screening", json={"ticker": "plx"})   # chữ thường vẫn được
        assert r.status_code == 202
        kq = doi_job(client, r.json()["job_id"])
        assert kq["status"] == "done", kq
        assert kq["ticker"] == "PLX"
        assert kq["run_id"] is not None
        assert 0 < len(kq["top"]) <= 20
        assert [b["rank"] for b in kq["top"]] == sorted(b["rank"] for b in kq["top"])


def test_ma_khong_co_trong_danh_muc():
    with TestClient(app) as client:
        r = client.post("/screening", json={"ticker": "XYZ"})
        assert r.status_code == 404


def test_job_khong_ton_tai():
    with TestClient(app) as client:
        assert client.get("/screening/999999").status_code == 404


def test_hai_job_lien_tiep_xep_hang():
    with TestClient(app) as client:
        ids = [client.post("/screening", json={"ticker": t}).json()["job_id"] for t in ["VIC", "ACB"]]
        for job_id in ids:
            assert doi_job(client, job_id)["status"] == "done"


def test_bao_cao_sau_screening():
    with TestClient(app) as client:
        job_id = client.post("/screening", json={"ticker": "PLX"}).json()["job_id"]
        kq = doi_job(client, job_id)
        assert kq["status"] == "done", kq

        r = client.get(f"/reports/{kq['run_id']}")
        assert r.status_code == 200
        bc = r.json()
        assert bc["ticker"] == "PLX"
        assert bc["report_md"].startswith("# Adverse Media Screening Report")
        assert bc["n_events"] == len(bc["events"])
        for ev in bc["events"]:
            assert ev["kiem_tra"]["trich_dan_hop_le"]   # số trích dẫn nằm trong danh sách nguồn


def test_bao_cao_chua_co():
    with TestClient(app) as client:
        assert client.get("/reports/999999").status_code == 404


class LLMHong:
    def hoi(self, user, system=None, max_tokens=2000):
        raise ConnectionError("API không phản hồi")


def test_llm_loi_thi_job_bao_loi_khong_ra_bao_cao_rong():
    """LLM hỏng thì job phải báo lỗi, không được ra báo cáo 'không có sự kiện' (âm tính giả)."""
    from app.services.llm import client
    cu = client._llm
    client._llm = LLMHong()
    try:
        with TestClient(app) as c:
            job_id = c.post("/screening", json={"ticker": "VPB"}).json()["job_id"]
            kq = doi_job(c, job_id)
            assert kq["status"] == "error"
            assert "LLM đọc lỗi" in kq["error"] and "API không phản hồi" in kq["error"]
            # job lỗi thì chưa có báo cáo
            assert c.get("/screening/%d" % job_id).json()["run_id"] is None
    finally:
        client._llm = cu


def test_llm_loi_o_buoc_bao_cao_van_bao_loi():
    """Bài đã đọc xong (có trong cache) nhưng LLM hỏng ở bước báo cáo: job vẫn phải báo lỗi."""
    from app.services.llm import client
    with TestClient(app) as c:
        # chạy bình thường một lần để có cache đọc bài
        assert doi_job(c, c.post("/screening", json={"ticker": "VHM"}).json()["job_id"])["status"] == "done"
        cu = client._llm
        client._llm = LLMHong()
        try:
            kq = doi_job(c, c.post("/screening", json={"ticker": "VHM"}).json()["job_id"])
            assert kq["status"] == "error" and "API không phản hồi" in kq["error"]
        finally:
            client._llm = cu

def test_bai_nhan_0_khong_vao_ket_qua():
    """Bài ER gắn nhãn 0 (nhắc tên nhưng không nói về công ty) không được lọt vào kết quả truy xuất."""
    from app.db import connection as db
    from app.services.er import label
    with TestClient(app) as c:
        kq = doi_job(c, c.post("/screening", json={"ticker": "VHM"}).json()["job_id"])
        assert kq["status"] == "done", kq
    con = db.corpus()
    bai_0 = {r[0] for r in con.execute("select article_id from er_labels where ticker = ? and model = ? and label = 0",
                                       ("VHM", label.ten_mo_hinh()))}
    bai_kq = {r[0] for r in con.execute("select article_id from run_results where run_id = ?", (kq["run_id"],))}
    con.close()
    assert bai_0, "DB mẫu cần có bài nhãn 0 của VHM để kiểm tra"
    assert not (bai_0 & bai_kq)
