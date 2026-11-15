import sqlite3
from datetime import datetime, timezone

import config


def corpus():
    con = sqlite3.connect(config.CORPUS_DB)
    con.executescript((config.BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
    return con


def companies():
    return sqlite3.connect(config.COMPANY_DB)


def now():
    return datetime.now(timezone.utc).isoformat()


def placeholders(values):
    return ",".join("?" * len(values))
