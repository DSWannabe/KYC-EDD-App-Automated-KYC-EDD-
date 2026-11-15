"""Gộp sự kiện, tóm tắt tiếng Anh theo 5W1H có trích dẫn, ghép báo cáo Markdown (port từ prod_04)."""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd

import config
import db
import llm
from llm_read import company_keys
from prompts import EVENT_PROMPT, GROUP_PROMPT, OVERVIEW_PROMPT
from text import pick_text


def risk_articles(con, run_id, ticker):
    df = pd.read_sql("""
        select r.rank, r.article_id, l.result, a.title, a.cleaned_text, a.published_at, a.source_url
        from run_results r
        join llm_reads l on l.ticker = ? and l.article_id = r.article_id and l.prompt_version = ?
        join articles a on a.id = r.article_id
        where r.run_id = ? and l.lien_quan = 1
        order by r.rank
    """, con, params=(ticker, config.PROMPT_VERSION, run_id)).fillna("")
    df["ngay"] = df["published_at"].astype(str).str[:10]
    return df.set_index("article_id", drop=False)


def group_events(ticker, row, risk):
    if len(risk) <= 1:
        return [[int(d)] for d in risk.article_id]
    lines = []
    for r in risk.itertuples():
        a = json.loads(r.result)
        lines.append(f"{r.article_id} | {r.ngay} | {a.get('loai_su_kien')} | {a.get('mo_ta')}")
    ans = llm.ask_json(GROUP_PROMPT.format(company=f"{ticker} - {row['full_name']}", lines="\n".join(lines)),
                       max_tokens=4000)

    valid = set(int(d) for d in risk.article_id)
    seen, groups = set(), []
    for grp in ans.get("groups", []):
        ids = [int(d) for d in grp if int(d) in valid and int(d) not in seen]
        seen.update(ids)
        if ids:
            groups.append(ids)
    groups += [[d] for d in sorted(valid - seen)]   # bài bị bỏ sót thành nhóm riêng
    return groups


def write_event(ticker, row, risk, grp):
    grp = sorted(grp, key=lambda d: risk.loc[d, "ngay"])[-config.MAX_SOURCES:]
    keys = company_keys(ticker, row)
    sources = []
    for n, d in enumerate(grp, start=1):
        text = pick_text(risk.loc[d, "cleaned_text"], keys, config.REPORT_MAX_CHARS, config.REPORT_HEAD_CHARS)
        sources.append(f"[{n}] {risk.loc[d, 'title']} ({risk.loc[d, 'ngay']})\n{text}")
    ev = llm.ask_json(EVENT_PROMPT.format(company=f"{row['full_name']} ({ticker})", sources="\n\n".join(sources)),
                      max_tokens=6000)
    ev["sources"] = [{"n": n, "id": int(d), "title": risk.loc[d, "title"], "date": risk.loc[d, "ngay"],
                      "url": risk.loc[d, "source_url"]} for n, d in enumerate(grp, start=1)]
    return ev


def check_event(ev):
    s = ev.get("summary", "")
    sentences = [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", s) if x.strip()]
    cited = [x for x in sentences if re.search(r"\[\d+\]", x)]
    nums = {int(n) for n in re.findall(r"\[(\d+)\]", s)}
    return {"cau_co_trich_dan": round(len(cited) / max(len(sentences), 1), 2),
            "trich_dan_hop_le": nums <= {x["n"] for x in ev["sources"]},
            "con_tieng_viet": bool(re.search(r"[À-ỹ]", s + ev.get("headline", "")))}


def profile_section(profile, ticker):
    leaders = "; ".join(x.strip() for x in str(profile.get("key_leaders", "")).split(";") if x.strip())
    return [
        "## Company profile", "",
        f"| | |", "|---|---|",
        f"| Legal name | {profile.get('company_name', '')} |",
        f"| Ticker | {ticker} |",
        f"| Tax code | {profile.get('tax_id', '')} |",
        f"| Industry | {profile.get('industry', '')} |",
        f"| Address | {profile.get('address', '')} |",
        f"| Key leaders | {leaders} |",
        f"| Website | {profile.get('website', '')} |",
        "",
        "*Profile fields are taken from the company catalog and kept in their original language.*", "",
    ]


def add_events(lines, events):
    for k, e in enumerate(events, start=1):
        lines.append(f"### {k}. {e.get('headline')}")
        lines.append(f"**Date:** {e.get('date')} | **Category:** {e.get('category')}")
        lines.append("")
        lines.append(e.get("summary", ""))
        lines.append("")
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", e.get("summary", ""))}
        for s in e["sources"]:
            if not cited or s["n"] in cited:      # chỉ liệt kê nguồn được trích dẫn
                lines.append(f"- [{s['n']}] {s['title']} ({s['date']}) {s['url']}")
        lines.append("")


def build(con, run_id, ticker, row, profile, read_summary):
    risk = risk_articles(con, run_id, ticker)
    groups = group_events(ticker, row, risk)

    events, errors = [], []
    with ThreadPoolExecutor(max_workers=config.WORKERS) as pool:
        futures = [pool.submit(write_event, ticker, row, risk, grp) for grp in groups]
        for f in as_completed(futures):
            try:
                events.append(f.result())
            except Exception as e:
                errors.append(str(e)[:100])
    events = sorted(events, key=lambda e: str(e.get("date", "")), reverse=True)
    for e in events:
        e["check"] = check_event(e)

    company = f"{row['full_name']} ({ticker})"
    if events:
        items = "\n".join(f"- {e.get('date')} | {e.get('category')} | {e.get('headline')}" for e in events)
        ov = llm.ask_json(OVERVIEW_PROMPT.format(company=company, items=items), max_tokens=3000)
    else:
        ov = {"company_name_en": "", "overview": "No adverse events were confirmed in the screened news."}

    cutoff = str(datetime.now().year - config.RECENT_YEARS)
    recent = [e for e in events if str(e.get("date", "")) >= cutoff]
    older = [e for e in events if str(e.get("date", "")) < cutoff]
    funnel = con.execute("select n_mention, n_bm25, n_top, date_from from screening_runs where run_id = ?",
                         (run_id,)).fetchone()
    name_en = ov.get("company_name_en") or profile.get("company_name", ticker)

    lines = [f"# Adverse Media Screening Report: {name_en} ({ticker})", "",
             f"*Draft generated {datetime.now().strftime('%Y-%m-%d')} for analyst review. Run id {run_id}.*", ""]
    if read_summary["n_error"]:
        lines += [f"**Warning: {read_summary['n_error']} of the top {read_summary['depth']} articles could not be read "
                  f"by the LLM. Adverse events in those articles may be missing.**", ""]
    lines += profile_section(profile, ticker)
    lines += ["## Overview", "", ov.get("overview", ""), "",
              f"## Adverse events in the last {config.RECENT_YEARS} years ({len(recent)})", ""]
    add_events(lines, recent)
    if older:
        lines += [f"## Earlier events ({len(older)})", ""]
        add_events(lines, older)

    khop = read_summary.get("ty_le_khop")
    lines += ["## Method", "",
              f"News articles linked to the company by entity resolution: {funnel[0]}"
              f"{' (from ' + funnel[3] + ')' if funnel[3] else ''}. Articles with risk keywords: {funnel[1]}. "
              f"Re-ranked: {funnel[2]}. Read by LLM: {read_summary['n_read']} of the top {read_summary['depth']}. "
              f"Articles confirmed as adverse: {len(risk)}, grouped into {len(events)} events.",
              f"Evidence quotes found verbatim in source articles: "
              f"{'n/a' if khop is None else f'{khop:.0%}'}.", ""]
    if errors:
        lines += [f"*{len(errors)} event(s) could not be summarised and are missing from this draft.*", ""]

    report_md = "\n".join(lines)
    con.execute("insert or replace into reports values (?, ?, ?, ?, ?, ?)",
                (run_id, ticker, len(events), report_md, json.dumps(events, ensure_ascii=False), db.now()))
    con.commit()
    return report_md, events
