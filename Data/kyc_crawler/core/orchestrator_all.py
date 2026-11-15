"""
Cao masothue nhieu cong ty, an toan khi gap loi.
- Doc truy van tu companies.yml (hoac --queries-file), moi truy van lay --pages trang.
- Trang nao cao roi thi bo qua (chay lai khong mat gi).
- Dung ngay khi bi chan (403/429) hoac loi lien tiep nhieu lan.
Chay tu thu muc kyc_crawler:  python -m core.orchestrator_batch --pages 2
"""

import argparse
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests
import yaml

from core.fetcher import fetch
from core.orchestrator import load_enabled_sources
from core.registry import get_parser
from core.storage import get_connection, init_db, insert_records, log_page, page_done

DEFAULT_COMPANIES = Path(__file__).resolve().parents[1] / "config" / "companies_v2.yml"


def read_queries(args):
    """Lay danh sach truy van tu file txt hoac companies.yml."""
    if args.queries_file:
        lines = Path(args.queries_file).read_text(encoding="utf-8").splitlines()
        return [l.strip() for l in lines if l.strip()]
    companies = yaml.safe_load(open(args.companies, encoding="utf-8"))["confounders"]
    if args.only:
        wanted = {t.upper() for t in args.only}
        companies = [c for c in companies if c["ticker"] in wanted]
    return [c["query"] for c in companies]


def count_rows():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()
    return n

def fetch_with_retry(url, name, rate_limit, args):
    """Goi fetch. Neu bi 429 thi nghi roi thu lai chinh URL do."""
    for attempt in range(args.max_waits + 1):
        try:
            return fetch(url, name, rate_limit)
        except requests.HTTPError as e:
            is_429 = e.response is not None and e.response.status_code == 429
            if not is_429 or attempt == args.max_waits:
                raise  # loi khac, hoac da cho het so lan cho phep
            wait = args.cooldown
            retry_after = e.response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = max(wait, int(retry_after))
            print(f"  [429] nghi {wait}s roi thu lai ({attempt + 1}/{args.max_waits})")
            time.sleep(wait)

def crawl_query(source, query, args, state):
    """Cao cac trang cua 1 truy van. Tra ve False neu phai dung ca lan chay."""
    name = source["name"]
    parse = get_parser(name)

    for page in range(1, args.pages + 1):
        if page_done(name, query, page):
            continue

        url = source["search_url_template"].format(query=quote_plus(query))
        if page > 1:
            url += f"&page={page}"

        try:
            html = fetch_with_retry(url, name, source.get("rate_limit_seconds", 2), args)
        except requests.RequestException as e:
            code = getattr(e.response, "status_code", None)
            state["errors"] += 1
            print(f"  [loi] {query!r} trang {page}: {code or type(e).__name__}")
            if code in (403, 429) or state["errors"] >= args.max_errors:
                print("DUNG: bi chan hoac loi lien tiep. Doi lau roi chay lai (tien do da luu).")
                return False
            break  # bo cac trang con lai cua truy van nay

        state["errors"] = 0  # request thanh cong thi dat lai bo dem loi
        records = parse(html)
        if not records:
            print(f"  [trong] {query!r} trang {page}: khong co ket qua")
            break

        insert_records(name, query, records)
        log_page(name, query, page, len(records))
        print(f"  {query!r} trang {page}: {len(records)} ket qua")
        time.sleep(args.delay)

    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", default=str(DEFAULT_COMPANIES))
    ap.add_argument("--queries-file", help="file txt, moi dong 1 truy van")
    ap.add_argument("--only", nargs="+", help="chi chay cac ticker nay")
    ap.add_argument("--limit", type=int, default=0, help="chi chay N truy van dau, de thu")
    ap.add_argument("--pages", type=int, default=1, help="so trang moi truy van")
    ap.add_argument("--delay", type=float, default=3, help="giay nghi them sau moi trang")
    ap.add_argument("--max-errors", type=int, default=3, help="dung sau N loi lien tiep")
    ap.add_argument("--cooldown", type=int, default=180, help="giay nghi khi bi 429")
    ap.add_argument("--max-waits", type=int, default=3, help="so lan nghi toi da cho moi trang")
    args = ap.parse_args()

    init_db()
    queries = read_queries(args)
    if args.limit:
        queries = queries[:args.limit]

    before = count_rows()
    state = {"errors": 0}
    print(f"Chay {len(queries)} truy van, {args.pages} trang moi truy van")

    stopped = False
    for source in load_enabled_sources():
        for query in queries:
            if not crawl_query(source, query, args, state):
                stopped = True
                break
        if stopped:
            break

    print(f"Xong. Them {count_rows() - before} cong ty moi (tong {count_rows()}).")
