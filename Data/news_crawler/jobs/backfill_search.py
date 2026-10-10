"""
Tim bai CU qua trang tim kiem noi bo cua cac bao (khoi `search:` trong config/news_sources.yml),
dua URL tim duoc vao cung luong tai -> lam sach -> chong trung -> luu voi crawl_daily.
Truy van da tim xong duoc ghi lai, chay lai se bo qua (dung --force de tim lai).

    python -m jobs.backfill_search --site vnexpress --query vingroup --pages 3 --dry-run
    python -m jobs.backfill_search --site all --queries-file queries.txt --pages 3
    python -m jobs.backfill_search --site tuoitre dantri --query "Vingroup" --from-ts 1577836800 --to-ts 1609459199
"""

import argparse
import time
from pathlib import Path

import yaml

from adapters import generic
from core import storage
from core.fetcher import Fetcher, make_session
from jobs.crawl_daily import DEFAULT_CONFIG, STAT_KEYS, ingest_items

DEBUG_DIR = Path(__file__).parent.parent / "data" / "debug"


RETRY_WAITS = [30, 90]   # giay doi truoc moi lan thu lai khi tai trang loi


def collect_urls(src, fetcher, defaults, query, pages, from_ts, to_ts, verbose):
    """Tra ve (danh sach URL, hoan_thanh, ly_do). ly_do: ok / robots / error / no_results.
    hoan_thanh=False neu bi robots chan hoac loi mang giua chung."""
    name, domain, search = src["name"], src["domain"], src["search"]
    delay = src.get("delay_between_requests", defaults["delay_between_requests"])
    items, seen = [], set()
    for page in range(1, pages + 1):
        url = generic.build_url(search, query, page, from_ts, to_ts)
        if not fetcher.allowed(url):
            print(f"  [{name}] robots.txt khong cho phep tim kiem tai {url}")
            return items, False, "robots"

        html = fetcher.get(url)
        time.sleep(delay)
        for wait in RETRY_WAITS:
            if html is not None:
                break
            print(f"  [{name}] loi tai trang {page}, doi {wait}s roi thu lai: {url}")
            time.sleep(wait)
            html = fetcher.get(url)
            time.sleep(delay)
        if html is None:
            print(f"  [{name}] loi tai trang {page} sau {len(RETRY_WAITS)} lan thu lai: {url}")
            return items, False, "error"

        found = generic.parse_results(search, domain, html, url)
        if not found:
            if verbose or page == 1:
                print(f"  [{name}] '{query}' trang {page}: khong thay ket qua")
            if page == 1:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                path = DEBUG_DIR / f"{name}_search_page1.html"
                path.write_bytes(html if isinstance(html, bytes) else html.encode("utf-8"))
                print(f"  da luu HTML de kiem tra: {path}  (neu truy van chac chan co ket qua thi sua link_selector/url trong config)")
            break
        new = [i for i in found if i["url"] not in seen]
        if not new:
            print(f"  [{name}] '{query}' trang {page}: lap lai ket qua trang truoc -> dung "
                  f"(het ket qua, hoac tham so phan trang trong config sai)")
            break
        seen.update(i["url"] for i in new)
        items.extend(new)
        if verbose:
            print(f"  [{name}] '{query}' trang {page}: {len(found)} ket qua ({len(new)} moi)")
    return items, True, ("ok" if items else "no_results")


def read_queries(args):
    queries = list(args.query)
    if args.queries_file:
        for line in Path(args.queries_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                queries.append(line)
    return list(dict.fromkeys(queries))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", nargs="+", required=True, help="ten bao trong config, hoac 'all'")
    ap.add_argument("--query", action="append", default=[], help="co the lap lai nhieu lan")
    ap.add_argument("--queries-file", help="file text, moi dong 1 truy van (dong bat dau bang # la ghi chu)")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--from-ts", type=int, default=0)
    ap.add_argument("--to-ts", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="toi da N bai moi tai ve / (bao, truy van); dung de thu")
    ap.add_argument("--dry-run", action="store_true", help="chi liet ke URL, khong tai bai, khong ghi DB")
    ap.add_argument("--force", action="store_true", help="tim lai ca truy van da hoan thanh truoc do")
    ap.add_argument("--max-empty", type=int, default=5,
                    help="dung 1 bao sau N truy van lien tiep bi loi, hoac khong co ket qua khi bao chua tung "
                         "tra ket qua nao (nhieu kha nang cau hinh sai). Khi bao da chay dung, truy van "
                         "khong co ket qua khong bi tinh.")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    queries = read_queries(args)
    if not queries:
        ap.error("can it nhat 1 --query hoac --queries-file")

    config = yaml.safe_load(open(args.config, encoding="utf-8"))
    defaults = config["defaults"]
    with_search = {s["name"]: s for s in config["sources"] if s.get("search")}
    names = sorted(with_search) if args.site == ["all"] else args.site
    unknown = [n for n in names if n not in with_search]
    if unknown:
        ap.error(f"chua co khoi `search:` trong config cho: {', '.join(unknown)} (co san: {', '.join(sorted(with_search))})")

    fetcher = Fetcher(make_session(defaults["user_agent"]), defaults["robots_agent"], defaults["request_timeout"])
    conn = None if args.dry_run else storage.connect(args.db)
    total = dict.fromkeys(STAT_KEYS, 0)

    outcome = {}
    for name in names:
        src = with_search[name]
        searched, urls_found, bad_streak, outcome[name] = 0, 0, 0, "xong"
        ever_ok = False          # bao nay da tung tra ket qua trong lan chay nay chua (= cau hinh da chay dung)
        for query in queries:
            if conn and not args.force and storage.search_pages_done(conn, name, query, args.from_ts, args.to_ts) >= args.pages:
                print(f"[{name}] '{query}': da tim truoc do, bo qua")
                continue
            items, complete, reason = collect_urls(src, fetcher, defaults, query, args.pages,
                                                   args.from_ts, args.to_ts, args.verbose)
            if reason == "robots":
                outcome[name] = "BI ROBOTS.TXT CHAN -> bo ca bao, khong tim kiem"
                break

            # Bo dem ngat: loi luon bi tinh; khong co ket qua chi bi tinh khi bao chua tung chay dung.
            # Khi bao da tra ket qua it nhat 1 lan, 0 ket qua nghia la cong ty do khong co tin -> khong tinh.
            if reason == "ok":
                ever_ok = True
                bad_streak = 0
            elif reason == "error" or (reason == "no_results" and not ever_ok):
                bad_streak += 1

            searched += 1
            urls_found += len(items)

            if args.dry_run:
                print(f"[{name}] '{query}': {len(items)} URL")
                for it in items:
                    print(f"   {it['url']}  |  {it['title']}")
            else:
                stats = ingest_items(conn, name, items, defaults, fetcher, args.limit, via=f"search:{name}:{query}")
                for k in total:
                    total[k] += stats[k]
                if complete and reason == "ok" and not args.limit:   # 0 ket qua co the do cau hinh sai -> khong danh dau da xong
                    storage.log_search(conn, name, query, args.from_ts, args.to_ts, args.pages, len(items))
                print(f"[{name}] '{query}': {len(items)} URL | " +
                      " ".join(f"{k}={stats[k]}" for k in STAT_KEYS if k != "feed_errors"))

            if bad_streak >= args.max_empty:
                if ever_ok:
                    why = "bi loi tai trang (co the bi chan tam thoi) -> doi mot luc, tang delay_between_requests"
                else:
                    why = ("bi loi hoac khong co ket qua ngay tu dau -> kiem tra url, link_selector, q_encoding "
                           "trong config (HTML mau trong data/debug/)")
                outcome[name] = f"DUNG sau {bad_streak} truy van lien tiep {why}"
                print(f"  [{name}] {outcome[name]}")
                break
        outcome[name] = f"{outcome[name]} | {searched} truy van, {urls_found} URL"

    print("\n[TONG KET THEO BAO]")
    for name, text in outcome.items():
        print(f"  {name:<12} {text}")
    if conn:
        print("[TONG] " + " ".join(f"{k}={total[k]}" for k in STAT_KEYS if k != "feed_errors"))
        conn.close()


if __name__ == "__main__":
    main()