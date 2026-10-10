"""
Chi lo viec goi HTTP va luu lai HTML tho.
Khong biet gi ve site cu the hay cach parse - de viec do cho parsers/.
"""

import time
from pathlib import Path
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def fetch(url: str, source_name: str, rate_limit_seconds: int = 2) -> str:
    """Goi URL, luu HTML tho vao data/raw/, tra ve noi dung HTML."""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    raw_path = RAW_DIR / f"{source_name}_{timestamp}.html"
    raw_path.write_text(resp.text, encoding="utf-8")

    time.sleep(rate_limit_seconds)  # lich su voi server, tranh bi chan
    return resp.text
