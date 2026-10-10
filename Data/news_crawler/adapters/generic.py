"""
Adapter tim kiem dung chung cho moi bao, cau hinh bang YAML (khong can viet code cho tung bao).
Cac khoa trong khoi `search:` cua tung nguon trong config/news_sources.yml:
  url            mau URL tim kiem, dung duoc {q} {page} {from_ts} {to_ts}
  q_encoding     plus (mac dinh "a+b") | percent ("a%20b") | slug ("a-b", bo dau)
  first_page     gia tri {page} cua trang dau (mac dinh 1; kieu offset thi 0)
  page_step      moi trang tang bao nhieu (mac dinh 1; kieu offset thi = so ket qua / trang)
  link_selector  CSS chon link tieu de cua ket qua (mac dinh "h3 a[href]")
  article_regex  regex nhan dien URL bai bao (mac dinh: slug + duoi .htm/.html/.chn/.tpo/.ldo)
  exclude_hosts  cac host bo qua (video, ban tieng Anh...)
"""

import re
import unicodedata
from urllib.parse import quote, quote_plus, urljoin, urlsplit

from bs4 import BeautifulSoup

DEFAULT_ARTICLE_REGEX = r"-[^/]+\.(?:htm|html|chn|tpo|ldo)$"
NON_ARTICLE_PATH = re.compile(r"/(?:tag|tags|chu-de|topic|su-kien|event|tim-kiem|video|podcast|anh|infographic)/")


def _encode_query(query: str, style: str) -> str:
    if style == "percent":
        return quote(query)
    if style == "slug":
        s = unicodedata.normalize("NFD", query.lower().replace("đ", "d"))
        s = "".join(c for c in s if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return quote_plus(query)


def build_url(search: dict, query: str, page: int = 1, from_ts: int = 0, to_ts: int = 0) -> str:
    page_value = search.get("first_page", 1) + (page - 1) * search.get("page_step", 1)
    return (search["url"]
            .replace("{q}", _encode_query(query, search.get("q_encoding", "plus")))
            .replace("{page}", str(page_value))
            .replace("{from_ts}", str(from_ts))
            .replace("{to_ts}", str(to_ts)))


def _is_article(url: str, search: dict, domain: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https"):
        return False
    if not (host == domain or host.endswith("." + domain)) or host in search.get("exclude_hosts", []):
        return False
    if NON_ARTICLE_PATH.search(parts.path):
        return False
    return bool(re.search(search.get("article_regex", DEFAULT_ARTICLE_REGEX), parts.path))


def parse_results(search: dict, domain: str, html: bytes | str, page_url: str) -> list[dict]:
    """Lay link bai bao tu trang ket qua. Dung link_selector de chi lay ket qua tim kiem,
    tranh link o thanh ben / chan trang."""
    soup = BeautifulSoup(html, "lxml")
    items, seen = [], set()
    for a in soup.select(search.get("link_selector", "h3 a[href]")):
        url = urljoin(page_url, a["href"]).split("#")[0].strip()
        if url in seen or not _is_article(url, search, domain):
            continue
        seen.add(url)
        items.append({"url": url,
                      "title": a.get("title") or a.get_text(" ", strip=True) or None,
                      "published_at": None})   # trang ket qua thuong khong co ngay; lay tu trang bai bao
    return items