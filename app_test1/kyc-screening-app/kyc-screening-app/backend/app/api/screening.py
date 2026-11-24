from fastapi import APIRouter, HTTPException

from app.db import connection as db
from app.schemas.screening import JobMoi, JobTrangThai, ScreeningRequest
from app.services import job_runner, screening

router = APIRouter(prefix="/screening", tags=["screening"])

SO_BAI_TRA_VE = 20


@router.post("", status_code=202, response_model=JobMoi)
def tao_screening(req: ScreeningRequest):
    """Bắt đầu screening cho một mã, trả về job_id ngay. Hỏi trạng thái bằng GET /screening/{job_id}."""
    ticker = req.ticker.strip().upper()
    con = db.company()
    co = con.execute("select 1 from company_names where ticker = ?", (ticker,)).fetchone()
    con.close()
    if not co:
        raise HTTPException(404, f"Mã {ticker} không có trong danh mục")

    job_id = job_runner.gui("screening", ticker, lambda cap_nhat: screening.chay_screening(ticker, cap_nhat))
    return {"job_id": job_id}


@router.get("/{job_id}", response_model=JobTrangThai)
def trang_thai(job_id: int):
    con = db.corpus()
    try:
        job = con.execute("select * from jobs where job_id = ?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, "Không có job này")
        kq = {k: job[k] for k in ["job_id", "ticker", "status", "step", "run_id", "error"]}

        if job["status"] == "done" and job["run_id"]:
            rows = con.execute("""
                select r.rank, r.article_id, a.title, a.published_at, a.source_url,
                       r.bm25_rank, r.dense_rank, r.ce_score, r.final
                from run_results r join articles a on a.id = r.article_id
                where r.run_id = ? order by r.rank limit ?
            """, (job["run_id"], SO_BAI_TRA_VE)).fetchall()
            kq["top"] = [dict(r) for r in rows]
        return kq
    finally:
        con.close()
