import re
import unicodedata

DOI_DAU = {
    "oà": "òa", "oá": "óa", "oả": "ỏa", "oã": "õa", "oạ": "ọa",
    "oè": "òe", "oé": "óe", "oẻ": "ỏe", "oẽ": "õe", "oẹ": "ọe",
    "uỳ": "ùy", "uý": "úy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy",
}
BANG_DOI_DAU = {**DOI_DAU, **{k.capitalize(): v.capitalize() for k, v in DOI_DAU.items()}}
DOI_DAU_RE = re.compile(r"(?<![qQ])(" + "|".join(BANG_DOI_DAU) + r")(?!\w)")


def chuan_hoa(text):
    # NFC và thống nhất vị trí dấu thanh: "hoà" -> "hòa"
    text = unicodedata.normalize("NFC", str(text or ""))
    return DOI_DAU_RE.sub(lambda m: BANG_DOI_DAU[m.group(1)], text)


def full_text(title, body):
    # Chuỗi dùng để đánh vị trí lần nhắc: tiêu đề, xuống dòng, nội dung
    return chuan_hoa(f"{title or ''}\n{body or ''}")


def bo_dau(text):
    text = unicodedata.normalize("NFD", chuan_hoa(text).lower()).replace("đ", "d")
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def squash(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def pick_text(text, keys, max_chars, head_chars):
    # Bài dài: giữ phần đầu, rồi thêm các đoạn quanh chỗ nhắc tên công ty
    if len(text) <= max_chars:
        return text
    spots = sorted({m.start() for k in keys for m in re.finditer(re.escape(k), text) if m.start() > head_chars})
    parts = [text[:head_chars]]
    used = head_chars
    last_end = head_chars
    for p in spots:
        if p < last_end:
            continue
        start, end = max(last_end, p - 600), p + 900
        parts.append(text[start:end])
        used += end - start
        last_end = end
        if used >= max_chars:
            break
    return "\n[...]\n".join(parts)
