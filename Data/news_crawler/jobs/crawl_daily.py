"""
Job crawl hang ngay: RSS/sitemap -> URL moi -> bo URL da co trong DB -> tai + lam sach
-> bo bai trung noi dung -> luu. Chay lai bao nhieu lan cung an toan (idempotent).

    python -m jobs.crawl_daily                    # tat ca nguon enabled
    python -m jobs.crawl_daily --only vnexpress   # 1 nguon
    python -m jobs.crawl_daily --discover-only    # chi kiem tra feed, khong tai bai, khong ghi DB
    python -m jobs.crawl_daily --limit 20         # toi da 20 bai moi tai ve / nguon (de thu)
"""

import argparse
import time
from pathlib import Path

import yaml

from core import storage
from core.cleaner import clean
from core.dedup import canonicalize_url, content_hash
from core.discovery import discover
from core.fetcher import Fetcher, make_session

DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "news_sources.yml"
STAT_KEYS = ["discovered", "skipped_seen", "new_articles", "dup_content", "unusable", "failed", "feed_errors"]


def ingest_items(conn, source_name, items, defaults, fetcher, limit, via):
    """Xu ly danh sach URL: bo URL da co -> tai -> lam sach -> bo trung noi dung -> luu.
    Dung chung cho crawl hang ngay (via='feed') va tim bai cu (via='search:...')."""
    stats = dict.fromkeys(STAT_KEYS, 0)
    attempts = 0
    for item in items:
        stats["discovered"] += 1
        canonical = canonicalize_url(item["url"])

        if storage.mark_seen_if_exists(conn, canonical):      # cap 1: URL da co -> khong tai lai
            stats["skipped_seen"] += 1
            continue
        if limit and attempts >= limit:
            break
        attempts += 1

        if not fetcher.allowed(item["url"]):
            storage.save_unusable(conn, canonical, "blocked_robots", via)
            stats["unusable"] += 1
            continue

        html = fetcher.get(item["url"])
        time.sleep(defaults["delay_between_requests"])
        if html is None:
            stats["failed"] += 1       # loi mang: khong ghi vao DB, lan sau se thu lai
            continue

        doc = clean(html, defaults["min_text_chars"])
        if doc is None:
            storage.save_unusable(conn, canonical, "no_text", via)
            stats["unusable"] += 1
            continue

        result = storage.save_article(                          # cap 2: noi dung da co -> chi them URL
            conn, canonical_url=canonical, source=source_name, source_url=item["url"],
            title=doc["title"] or item["title"],
            published_at=item["published_at"] or doc["date"],
            text=doc["text"], chash=content_hash(doc["text"]), via=via,
        )
        stats["new_articles" if result == "new" else "dup_content"] += 1

    return stats


def crawl_source(conn, src, defaults, session, fetcher, limit):
    found = discover(src, defaults, session)
    for feed_url, err in found["errors"]:
        print(f"  [feed loi] {feed_url}: {err}")
    stats = ingest_items(conn, src["name"], found["items"], defaults, fetcher, limit, via="feed")
    stats["feed_errors"] = len(found["errors"])
    return stats


def check_feeds(sources, defaults, session):
    for src in sources:
        found = discover(src, defaults, session)
        print(f"[{src['name']}]")
        for feed_url, n in found["by_feed"].items():
            print(f"  OK   {n:>3} bai  {feed_url}")
        for feed_url, err in found["errors"]:
            print(f"  LOI  {feed_url}  ->  {err}")
        for item in found["items"][:3]:
            print(f"       vd: {item['title']}  ({item['url']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--db", default=None)
    ap.add_argument("--only", default=None)
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    config = yaml.safe_load(open(args.config, encoding="utf-8"))
    defaults = config["defaults"]
    sources = [s for s in config["sources"]
               if s.get("enabled", True) and (not args.only or s["name"] == args.only)]

    session = make_session(defaults["user_agent"])
    if args.discover_only:
        check_feeds(sources, defaults, session)
        return

    conn = storage.connect(args.db)
    fetcher = Fetcher(session, defaults["robots_agent"], defaults["request_timeout"])
    total = dict.fromkeys(STAT_KEYS, 0)

    for src in sources:
        run_id = storage.start_run(conn, src["name"])
        stats = crawl_source(conn, src, defaults, session, fetcher, args.limit)
        storage.finish_run(conn, run_id, stats)
        print(f"[{src['name']}] " + " ".join(f"{k}={stats[k]}" for k in STAT_KEYS))
        for k in STAT_KEYS:
            total[k] += stats[k]

    print("[TONG] " + " ".join(f"{k}={total[k]}" for k in STAT_KEYS))
    conn.close()


if __name__ == "__main__":
    main()