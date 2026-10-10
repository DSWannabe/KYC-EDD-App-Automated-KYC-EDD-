"""
Lay danh sach URL bai moi tu RSS hoac sitemap cua tung bao (khong dung search engine).
Tra ve: {"items": [{url, title, published_at}], "by_feed": {feed_url: so_bai}, "errors": [(feed_url, loi)]}
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import feedparser

from core.dedup import host_matches

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "news": "http://www.google.com/schemas/sitemap-news/0.9"}
MAX_CHILD_SITEMAPS = 10


def _struct_to_iso(t):
    return datetime(*t[:6], tzinfo=timezone.utc).isoformat() if t else None


def _parse_dt(s):
    try:
        dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_recent(s, days):
    dt = _parse_dt(s)
    return True if dt is None else dt >= datetime.now(timezone.utc) - timedelta(days=days)


def discover_rss(feed_url, session, timeout):
    resp = session.get(feed_url, timeout=timeout)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    if not parsed.entries and parsed.bozo:
        raise ValueError(f"khong doc duoc feed: {parsed.bozo_exception}")
    return [
        {"url": e["link"], "title": e.get("title"),
         "published_at": _struct_to_iso(e.get("published_parsed") or e.get("updated_parsed"))}
        for e in parsed.entries if e.get("link")
    ]


def discover_sitemap(url, session, timeout, max_age_days=2, depth=0):
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    kind = root.tag.split("}")[-1]
    items = []

    if kind == "sitemapindex" and depth < 1:
        followed = 0
        for sm in root.findall("sm:sitemap", NS):
            lastmod = sm.findtext("sm:lastmod", namespaces=NS)
            if lastmod and not _is_recent(lastmod, max_age_days):
                continue
            if followed >= MAX_CHILD_SITEMAPS:
                break
            followed += 1
            items += discover_sitemap(sm.findtext("sm:loc", namespaces=NS).strip(),
                                      session, timeout, max_age_days, depth + 1)
    elif kind == "urlset":
        for u in root.findall("sm:url", NS):
            lastmod = (u.findtext("sm:lastmod", namespaces=NS)
                       or u.findtext("news:news/news:publication_date", namespaces=NS))
            if lastmod and not _is_recent(lastmod, max_age_days):
                continue
            items.append({"url": u.findtext("sm:loc", namespaces=NS).strip(),
                          "title": u.findtext("news:news/news:title", namespaces=NS),
                          "published_at": lastmod})
    return items


def discover(source, defaults, session):
    timeout, cap = defaults["request_timeout"], defaults["max_items_per_feed"]
    items, by_feed, errors = [], {}, []

    for feed in source.get("feeds", []):
        try:
            if feed["type"] == "rss":
                found = discover_rss(feed["url"], session, timeout)
            elif feed["type"] == "sitemap":
                found = discover_sitemap(feed["url"], session, timeout, feed.get("max_age_days", 2))
            else:
                raise ValueError(f"type khong ho tro: {feed['type']}")
        except Exception as e:
            errors.append((feed["url"], repr(e)))
            continue

        found = [i for i in found if host_matches(i["url"], source["domain"])][:cap]
        by_feed[feed["url"]] = len(found)
        items.extend(found)

    return {"items": items, "by_feed": by_feed, "errors": errors}