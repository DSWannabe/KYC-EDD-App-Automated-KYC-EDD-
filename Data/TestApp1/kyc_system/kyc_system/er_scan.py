"""ER bước 1-2: quét alias trong bài và kiểm tra từng lần nhắc."""
import re

from text import full_text


def find_spans(full, pattern, is_name):
    # Tên pháp nhân: so khớp không phân biệt hoa thường, có ranh giới từ
    if is_name:
        mau = rf"(?<!\w){re.escape(pattern)}(?!\w)"
        return [m.span() for m in re.finditer(mau, full.lower())]
    return [m.span() for m in re.finditer(pattern, full)]


def inside(start, end, spans):
    return any(s <= start and end <= e for s, e in spans)


def scan_article(res, article_id, title, body):
    full = full_text(title, body)
    title_len = len(full.split("\n", 1)[0])
    cache = {}

    def spans(pattern, is_name):
        key = (pattern, is_name)
        if key not in cache:
            cache[key] = find_spans(full, pattern, is_name)
        return cache[key]

    mentions = []
    for m in res.alias_re.finditer(full):
        start, end = m.span()
        for ticker, loai, alias in res.lookup(m.group(1)):
            ten = next((x for x in res.ten_dai_hon.get((ticker, alias), []) if inside(start, end, spans(x, True))), "")
            luat = next((p for p in res.exclusions.get(ticker, []) if inside(start, end, spans(p, False))), "")
            mentions.append({
                "article_id": article_id,
                "ticker": ticker,
                "alias": alias,
                "chuoi_khop": m.group(1),
                "loai_alias": loai,
                "start_pos": start,
                "end_pos": end,
                "trong_tieu_de": start < title_len,
                "ten_dai_hon": ten,
                "luat_loai_tru": luat,
                "sach": not ten and not luat,
            })
    return full, mentions
