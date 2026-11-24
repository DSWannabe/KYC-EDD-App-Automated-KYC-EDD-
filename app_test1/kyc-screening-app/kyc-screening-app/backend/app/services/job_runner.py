"""Chạy công việc nặng ở nền và ghi trạng thái vào bảng jobs.

Chỉ một worker: model và chỉ mục chiếm nhiều bộ nhớ, GPU cũng chỉ nên làm một việc một lúc.
Các yêu cầu đến sau xếp hàng (status = queued).
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.db import connection as db

_pool = ThreadPoolExecutor(max_workers=1)
COT_CHO_PHEP = {"status", "step", "run_id", "error"}


def _bay_gio():
    return datetime.now(timezone.utc).isoformat()


def gui(kind, ticker, ham):
    """Tạo job rồi chạy `ham(cap_nhat)` ở nền. `ham` trả về run_id. Trả về job_id."""
    con = db.corpus()
    cur = con.execute("insert into jobs (kind, ticker, status, step, created_at, updated_at) values (?, ?, ?, ?, ?, ?)",
                      (kind, ticker, "queued", "Đang chờ", _bay_gio(), _bay_gio()))
    con.commit()
    job_id = cur.lastrowid
    con.close()
    _pool.submit(_chay, job_id, ham)
    return job_id


def _chay(job_id, ham):
    con = db.corpus()

    def cap_nhat(**kw):
        assert set(kw) <= COT_CHO_PHEP
        cot = ", ".join(f"{k} = ?" for k in kw)
        con.execute(f"update jobs set {cot}, updated_at = ? where job_id = ?", (*kw.values(), _bay_gio(), job_id))
        con.commit()

    try:
        cap_nhat(status="running", step="Bắt đầu")
        run_id = ham(cap_nhat)
        cap_nhat(status="done", step="Xong", run_id=run_id)
    except Exception as e:
        cap_nhat(status="error", error=f"{type(e).__name__}: {e}")
    finally:
        con.close()
