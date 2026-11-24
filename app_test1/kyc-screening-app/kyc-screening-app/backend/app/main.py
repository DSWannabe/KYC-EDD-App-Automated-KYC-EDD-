"""Khởi động server: uvicorn app.main:app --port 8000 (chạy trong thư mục backend/)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api import lookup, reports, screening
from app.db import connection as db


@asynccontextmanager
async def lifespan(app):
    con = db.corpus()
    db.init_schema(con)   # tạo các bảng của app nếu chưa có
    con.close()
    yield


app = FastAPI(title="KYC screening", lifespan=lifespan)

# Cho frontend (Vite, cổng 5173) gọi API khi chạy thử
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

app.include_router(screening.router)
app.include_router(reports.router)
app.include_router(lookup.router)


@app.get("/health")
def health():
    return {"ok": True, "encoder_mode": config.ENCODER_MODE, "llm_mode": config.LLM_MODE}
