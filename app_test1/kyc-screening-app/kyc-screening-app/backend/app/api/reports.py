import json

from fastapi import APIRouter, HTTPException

from app.db import connection as db
from app.schemas.report import BaoCao

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{run_id}", response_model=BaoCao)
def lay_bao_cao(run_id: int):
    """Báo cáo của một lần screening. run_id lấy từ GET /screening/{job_id} khi status = done."""
    con = db.corpus()
    try:
        r = con.execute("select * from reports where run_id = ?", (run_id,)).fetchone()
    finally:
        con.close()
    if not r:
        raise HTTPException(404, "Chưa có báo cáo cho run này")
    return {"run_id": r["run_id"], "ticker": r["ticker"], "n_events": r["n_events"],
            "report_md": r["report_md"], "events": json.loads(r["detail"]), "created_at": r["created_at"]}
