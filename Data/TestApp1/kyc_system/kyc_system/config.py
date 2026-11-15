import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Database và API key
# Có thể ghi đè bằng biến môi trường, ví dụ để chạy trên DB thử
DATA_DIR = "/home/anhtupham99/kyc/KYC-EDD-App-Automated-KYC-EDD-/Data"
CORPUS_DB = os.environ.get("KYC_CORPUS_DB", f"{DATA_DIR}/news_crawler/data/corpus_test.db")
COMPANY_DB = os.environ.get("KYC_COMPANY_DB", f"{DATA_DIR}/kyc_crawler/data/companies.db")
ENV_FILE = os.environ.get("KYC_ENV_FILE", f"{DATA_DIR}/news_crawler/.env")
CATALOG_TABLE = "vn100_20261106"  # bảng danh mục công ty, có thể đổi khi cập nhật danh sách

MODEL_DIR = BASE_DIR / "models"
REPORT_DIR = BASE_DIR / "reports"

# Entity Resolution
ER_MODEL_FILE = MODEL_DIR / "er_lr_v1.joblib"
ER_RULE_VERSION = "r1"       # tăng khi sửa alias hoặc luật loại trừ, để job nền quét lại
ER_LOWER = 0.30              # xác suất dưới ngưỡng này: 0
ER_INCLUDE_REVIEW = True     # truy xuất dùng cả cặp "xem", để không bỏ sót bằng chứng
CONTEXT_WORDS = 5            # số từ mỗi bên alias
MAX_MENTIONS = 5             # số lần nhắc tối đa mỗi cặp khi lấy ngữ cảnh
ER_BATCH = 500               # số bài xử lý mỗi đợt trong job nền

# Vector bge-m3
EMBED_MODEL = "BAAI/bge-m3"
DEVICE = "cuda"
CHUNK_WORDS = 200
MAX_CHUNKS = 10
EMBED_BATCH = 200

# Truy xuất (giữ đúng cấu hình pipeline_v1 đã chốt)
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
PENALTY = 0.5
LAM = 0.05
RRF_K = 60
W = 0.25
TOP_N = 50
ALPHA = 0.3

# LLM
LLM_MODEL = "claude-haiku-5-5"
PROMPT_VERSION = "v2"
READ_FIRST = 20              # đọc 20 bài đầu
READ_STEP = 10               # mỗi đợt đọc thêm 10 bài
READ_MAX = 50
EXTEND_IF = 3                # đọc thêm khi 5 bài cuối có từ 3 bài rủi ro trở lên
MAX_CHARS = 8000
HEAD_CHARS = 3000
WORKERS = 8

# Báo cáo
RECENT_YEARS = 5
MAX_SOURCES = 3
REPORT_MAX_CHARS = 4000
REPORT_HEAD_CHARS = 2000
