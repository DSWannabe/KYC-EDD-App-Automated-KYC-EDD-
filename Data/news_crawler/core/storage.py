"""
Kho bai bao (SQLite), chong trung lap o 2 cap:
  - article_urls.canonical_url (PRIMARY KEY): URL da gap roi thi khong tai lai
  - articles.content_hash (UNIQUE): URL moi nhung noi dung da co thi chi them URL tro ve bai cu

Chinh sach: URL da co thi giu ban dau tien, khong cap nhat noi dung neu bao sua bai sau do.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "corpus.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,          -- URL goc luc gap lan dau
    title TEXT,
    published_at TEXT,
    cleaned_text TEXT NOT NULL,
    first_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS articles_published_idx ON articles (published_at);

CREATE TABLE IF NOT EXISTS article_urls (
    canonical_url TEXT PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id),   -- NULL neu trang khong dung duoc
    status TEXT NOT NULL DEFAULT 'ok',            -- ok / no_text / blocked_robots
    discovered_via TEXT,                          -- feed / search:<bao>:<truy van> (lan gap dau tien)
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    seen_count INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS article_urls_article_idx ON article_urls (article_id);

CREATE TABLE IF NOT EXISTS search_log (      -- truy van tim bai cu da hoan thanh (de chay lai khong lap)
    site TEXT NOT NULL,
    query TEXT NOT NULL,
    from_ts INTEGER NOT NULL,
    to_ts INTEGER NOT NULL,
    pages_requested INTEGER NOT NULL,
    urls_found INTEGER NOT NULL,
    searched_at TEXT NOT NULL,
    PRIMARY KEY (site, query, from_ts, to_ts)
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    discovered INTEGER, skipped_seen INTEGER, new_articles INTEGER,
    dup_content INTEGER, unusable INTEGER, failed INTEGER, feed_errors INTEGER
);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def connect(path=None) -> sqlite3.Connection:
    path = Path(path) if path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.executescript(SCHEMA)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(article_urls)")]
    if "discovered_via" not in cols:          # DB tao tu phien ban cu
        conn.execute("ALTER TABLE article_urls ADD COLUMN discovered_via TEXT")
        conn.commit()
    return conn


def mark_seen_if_exists(conn, canonical_url: str) -> bool:
    """Kiem tra URL da co trong DB chua; neu co thi cap nhat last_seen_at / seen_count."""
    cur = conn.execute(
        "UPDATE article_urls SET last_seen_at = ?, seen_count = seen_count + 1 WHERE canonical_url = ?",
        (_now(), canonical_url),
    )
    conn.commit()
    return cur.rowcount > 0


def save_article(conn, *, canonical_url, source, source_url, title, published_at, text, chash, via=None) -> str:
    """Tra ve 'new' (bai moi) hoac 'dup_content' (noi dung da co duoi URL khac)."""
    now = _now()
    row = conn.execute("SELECT id FROM articles WHERE content_hash = ?", (chash,)).fetchone()
    if row:
        article_id, result = row[0], "dup_content"
    else:
        cur = conn.execute(
            """INSERT INTO articles (content_hash, source, source_url, title, published_at,
                                     cleaned_text, first_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chash, source, source_url, title, published_at, text, now),
        )
        article_id, result = cur.lastrowid, "new"

    conn.execute(
        """INSERT OR IGNORE INTO article_urls
           (canonical_url, article_id, status, discovered_via, first_seen_at, last_seen_at)
           VALUES (?, ?, 'ok', ?, ?, ?)""",
        (canonical_url, article_id, via, now, now),
    )
    conn.commit()
    return result


def save_unusable(conn, canonical_url: str, status: str, via=None):
    """Ghi nho URL khong dung duoc de lan sau khong tai lai vo ich."""
    now = _now()
    conn.execute(
        """INSERT OR IGNORE INTO article_urls
           (canonical_url, article_id, status, discovered_via, first_seen_at, last_seen_at)
           VALUES (?, NULL, ?, ?, ?, ?)""",
        (canonical_url, status, via, now, now),
    )
    conn.commit()


def start_run(conn, source: str) -> int:
    cur = conn.execute("INSERT INTO crawl_runs (source, started_at) VALUES (?, ?)", (source, _now()))
    conn.commit()
    return cur.lastrowid


def finish_run(conn, run_id: int, s: dict):
    conn.execute(
        """UPDATE crawl_runs SET finished_at = ?, discovered = ?, skipped_seen = ?, new_articles = ?,
           dup_content = ?, unusable = ?, failed = ?, feed_errors = ? WHERE id = ?""",
        (_now(), s["discovered"], s["skipped_seen"], s["new_articles"], s["dup_content"],
         s["unusable"], s["failed"], s["feed_errors"], run_id),
    )
    conn.commit()


def search_pages_done(conn, site: str, query: str, from_ts: int, to_ts: int) -> int:
    """So trang da tim xong cho truy van nay (0 neu chua tim)."""
    row = conn.execute(
        "SELECT pages_requested FROM search_log WHERE site = ? AND query = ? AND from_ts = ? AND to_ts = ?",
        (site, query, from_ts, to_ts),
    ).fetchone()
    return row[0] if row else 0


def log_search(conn, site: str, query: str, from_ts: int, to_ts: int, pages: int, urls_found: int):
    conn.execute(
        "INSERT OR REPLACE INTO search_log VALUES (?, ?, ?, ?, ?, ?, ?)",
        (site, query, from_ts, to_ts, pages, urls_found, _now()),
    )
    conn.commit()