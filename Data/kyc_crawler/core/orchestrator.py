"""
Ghep fetcher + registry: doc config, fetch tung nguon enabled=true,
dispatch sang dung parser, luu ket qua JSON vao data/parsed/.
"""

from pathlib import Path
import yaml

from core.fetcher import fetch
from core.registry import get_parser
from core.storage import insert_records
from urllib.parse import quote_plus

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources_config.yml"


def load_enabled_sources():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return [s for s in config["sources"] if s.get("enabled", False)]


def run_query(query: str):
    """Chay 1 query qua tat ca nguon Tier 1 dang enabled, tra ve dict ket qua theo source."""
    sources = load_enabled_sources()
    results = {}

    for source in sources:
        url = source["search_url_template"].format(query=query)
        html = fetch(url, source["name"], source.get("rate_limit_seconds", 2))

        parse = get_parser(source["name"])
        records = parse(html)
        results[source["name"]] = records

        insert_records(source["name"], query, records)

    return results


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    import yaml

    # orchestrator.py -> core -> kyc_crawler -> Data
    DEFAULT_COMPANIES = Path(__file__).resolve().parents[2] / "kyc_crawler" / "config" / "companies.yml"

    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", default=str(DEFAULT_COMPANIES), help="file yml danh sach cong ty")
    ap.add_argument("--only", nargs="+", help="chi chay cac ticker nay, vd --only VIC FPT")
    ap.add_argument("--limit", type=int, default=0, help="chi chay N cong ty dau tien, de thu")
    args = ap.parse_args()

    companies = yaml.safe_load(open(args.companies, encoding="utf-8"))["companies"]
    if args.only:
        wanted = {t.upper() for t in args.only}
        companies = [c for c in companies if c["ticker"] in wanted]
    if args.limit:
        companies = companies[:args.limit]
    print(f"Chay {len(companies)} cong ty tu {args.companies}")

    for c in companies:
        q = c["query"]
        results = run_query(q)
        for source_name, records in results.items():
            first = records[0]["company_name"] if records else None
            print(f"[{c['ticker']}] [{q}] [{source_name}] {len(records)} ket qua | dau tien: {first}")