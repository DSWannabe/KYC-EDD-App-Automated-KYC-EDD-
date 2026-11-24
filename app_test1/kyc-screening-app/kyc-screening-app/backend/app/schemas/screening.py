from typing import List, Optional

from pydantic import BaseModel


class ScreeningRequest(BaseModel):
    ticker: str


class JobMoi(BaseModel):
    job_id: int


class BaiTop(BaseModel):
    rank: int
    article_id: int
    title: str
    published_at: Optional[str] = None
    source_url: Optional[str] = None
    bm25_rank: Optional[int] = None
    dense_rank: Optional[int] = None
    ce_score: Optional[float] = None
    final: Optional[float] = None


class JobTrangThai(BaseModel):
    job_id: int
    ticker: str
    status: str                       # queued | running | done | error
    step: Optional[str] = None        # bước đang chạy
    run_id: Optional[int] = None
    error: Optional[str] = None
    top: Optional[List[BaiTop]] = None   # chỉ có khi status = done
