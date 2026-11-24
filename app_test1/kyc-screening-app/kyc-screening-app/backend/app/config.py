"""Cấu hình: đường dẫn và tham số. Mọi giá trị có thể đổi bằng biến môi trường."""
import os
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent

# Mặc định trỏ vào DB mẫu 100 bài. Dùng DB thật thì đặt KYC_CORPUS_DB và KYC_COMPANY_DB.
DATA_DIR = Path(os.environ.get("KYC_DATA_DIR", PROJECT / "data" / "sample"))
CORPUS_DB = Path(os.environ.get("KYC_CORPUS_DB", DATA_DIR / "corpus.db"))
COMPANY_DB = Path(os.environ.get("KYC_COMPANY_DB", DATA_DIR / "companies.db"))

ENV_FILE = Path(os.environ.get("KYC_ENV_FILE", BACKEND / ".env"))   # chứa ANTHROPIC_API_KEY
MODELS_DIR = Path(os.environ.get("KYC_MODELS_DIR", BACKEND / "models"))
LOGS_DIR = Path(os.environ.get("KYC_LOGS_DIR", BACKEND / "logs"))

CATALOG = "vn100"   # tên bảng danh mục công ty trong companies.db

# Tham số retrieval đã chọn trên dev (b03 đến b06)
CAU_HINH_FILE = MODELS_DIR / "cau_hinh.json"

# real: bge-m3 và bge-reranker thật (cần torch, sentence-transformers; có GPU thì nhanh hơn)
# mock: encoder giả bằng băm từ, chỉ để kiểm tra luồng chạy, không dùng để đánh giá chất lượng
ENCODER_MODE = os.environ.get("KYC_ENCODER_MODE", "real")

# real: gọi Claude thật (cần ANTHROPIC_API_KEY trong .env)
# mock: trả kết quả giả theo từ khóa, chỉ để kiểm tra luồng chạy
LLM_MODE = os.environ.get("KYC_LLM_MODE", "real")
LLM_MODEL = "claude-haiku-5-5"
QUY_UOC_FILE = MODELS_DIR / "quy_uoc_gan_nhan_rui_ro_v4.md"   # system prompt khi LLM đọc bài
PROMPT_VERSION = "v4"

# ER nền: LLM chỉ xem lại các cặp mà mô hình chưa chắc (điểm nằm trong vùng xem lại)
# Vùng xem lại lấy từ er_model.json (train_er.py chọn trên dev); file chưa có thì dùng mặc định dưới đây
ER_XEM_LAI_MAC_DINH = (0.4, 0.7)
ER_LLM_SO_LAN = 5                                              # hỏi mỗi cặp 5 lần, lấy trung bình điểm
ER_LLM_TOI_DA = int(os.environ.get("KYC_ER_LLM_TOI_DA", 500))  # số cặp tối đa mỗi lần chạy, để giới hạn chi phí
ER_PROMPT_VERSION = "er_v2"
