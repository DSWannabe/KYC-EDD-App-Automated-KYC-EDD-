"""Chạy việc nền cho bài mới. Chạy trong thư mục backend/:  python -m jobs.run_background

Có thể đặt lịch (cron) chạy định kỳ sau khi crawler thêm bài.
"""
from app.services.background import chay_nen

if __name__ == "__main__":
    print("Xong:", chay_nen())
