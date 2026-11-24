from fastapi import APIRouter, HTTPException

from app.db import connection as db
from app.schemas.lookup import LookupRequest, LookupResponse
from app.services.lookup import lookup, model

router = APIRouter(prefix="/lookup", tags=["lookup"])


@router.post("", response_model=LookupResponse)
def tra_cuu(req: LookupRequest):
    """Đoạn văn + tên công ty -> một công ty duy nhất, tối đa 3 ứng viên cần xác nhận, hoặc không có."""
    if not req.doan.strip():
        raise HTTPException(422, "Đoạn văn trống")
    if not model.FILE.is_file():
        raise HTTPException(503, "Chưa có models/lookup_model.json. Chạy scripts/train_lookup.py trước.")
    con = db.company()
    try:
        return {"ket_qua": lookup.tra_cuu(con, req.doan, req.ten)}
    finally:
        con.close()
