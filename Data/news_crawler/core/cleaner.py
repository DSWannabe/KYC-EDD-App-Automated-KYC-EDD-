"""
Cat bo menu/quang cao, lay tieu de, ngay dang va noi dung chinh cua bai bao.
"""

import json

import trafilatura


def clean(html: bytes | str, min_chars: int = 300) -> dict | None:
    """Tra ve {title, date, text}, hoac None neu khong co noi dung du dai (trang rong, gallery, video...)."""
    raw = trafilatura.extract(html, output_format="json", with_metadata=True, include_comments=False)
    if not raw:
        return None
    doc = json.loads(raw)
    text = (doc.get("text") or "").strip()
    if len(text) < min_chars:
        return None
    return {"title": doc.get("title"), "date": doc.get("date"), "text": text}