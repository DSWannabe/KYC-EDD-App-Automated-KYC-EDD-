"""
Cac khoa chong trung lap cho bai bao:
  - canonical_url : cung 1 trang web (bo utm_*, #fragment, www., dau / cuoi...)
  - content_hash  : cung noi dung du URL khac nhau (bai dang lai, dang o nhieu chuyen muc)
"""

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"fbclid", "gclid", "gidzl", "zarsrc", "igshid", "mc_cid", "mc_eid", "ref_src"}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    try:
        port = parts.port
    except ValueError:
        port = None
    if port and port not in (80, 443):
        host = f"{host}:{port}"

    path = parts.path.rstrip("/") or "/"
    query = sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not (k.lower().startswith("utm_") or k.lower() in TRACKING_PARAMS)
    )
    return urlunsplit(("https", host, path, urlencode(query), ""))


def host_matches(url: str, domain: str) -> bool:
    """True neu URL thuoc domain (hoac subdomain cua domain) - loc link quang cao/ngoai site."""
    host = (urlsplit(url).hostname or "").lower()
    return host == domain or host.endswith("." + domain)


def normalize_text(text: str) -> str:
    # NFC quan trong voi tieng Viet: cung 1 chu co the duoc ma hoa dang to hop hoac dang tach dau
    text = unicodedata.normalize("NFC", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()