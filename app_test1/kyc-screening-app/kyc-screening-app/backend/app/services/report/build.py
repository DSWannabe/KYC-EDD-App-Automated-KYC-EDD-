"""Gộp sự kiện và viết báo cáo (tương đương p04 của kyc_v3).

1. Lấy các bài LLM kết luận là rủi ro trong top của run.
2. Gộp các bài cùng một sự việc thành một sự kiện (1 lần gọi LLM).
3. Tóm tắt từng sự kiện bằng tiếng Anh, 5W1H, có trích dẫn (gọi song song).
4. Viết phần tổng quan, ghép thành báo cáo Markdown, lưu vào bảng reports.
Báo cáo là bản nháp để chuyên viên rà soát, không phải kết luận cuối cùng.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from app import config
from app.services.common import ham_chung as hc
from app.services.llm import doc_bai
from app.services.llm.client import lay_llm
from app.services.report.prompts import EVENT_PROMPT, GROUP_PROMPT, OVERVIEW_PROMPT
from app.services.retrieval import prepare

RECENT_YEARS = 5    # sự kiện trong 5 năm gần nhất đưa lên mục chính, cũ hơn đưa xuống mục lịch sử
MAX_SOURCES = 3     # mỗi sự kiện đưa tối đa 3 bài nguồn cho LLM đọc
MAX_CHARS = 4000    # độ dài tối đa mỗi bài nguồn
HEAD_CHARS = 2000
WORKERS = 8


def _hoi_json(prompt, max_tokens=6000):
    return hc.doc_json(lay_llm().hoi(prompt, max_tokens=max_tokens))


# ---------- 1. Bài rủi ro ----------

def _bai_rui_ro(con, run_id, ticker):
    """Danh sách bài rủi ro của run, mỗi bài là dict. Khóa theo article_id."""
    rows = con.execute("""
        select r.rank, r.article_id, l.result, a.title, a.cleaned_text, a.published_at, a.source_url
        from run_results r
        join llm_reads l on l.ticker = ? and l.article_id = r.article_id and l.prompt_version = ?
        join articles a on a.id = r.article_id
        where r.run_id = ? and r.rank <= ? and l.lien_quan = 1
        order by r.rank
    """, (ticker, config.PROMPT_VERSION, run_id, doc_bai.TOP_K)).fetchall()

    bai = {}
    for r in rows:
        title = r["title"] or ""
        bai[r["article_id"]] = {
            "id": r["article_id"], "title": title,
            "noi_dung": hc.lam_sach_noi_dung(title, r["cleaned_text"] or ""),
            "ngay": str(r["published_at"] or "")[:10], "url": r["source_url"],
            "kq": json.loads(r["result"]),
        }
    return bai


# ---------- 2. Gộp sự kiện ----------

def _gop_su_kien(bai, company):
    """Trả về danh sách nhóm, mỗi nhóm là danh sách id bài cùng một sự kiện."""
    dong = [f"{b['id']} | {b['ngay']} | {b['kq'].get('loai')} | {b['kq'].get('mo_ta')}" for b in bai.values()]
    tra_loi = _hoi_json(GROUP_PROMPT.format(company=company, lines="\n".join(dong)), max_tokens=4000)

    # kiểm tra lại kết quả của LLM: bài lạ hoặc lặp thì bỏ, bài bị bỏ sót thành nhóm riêng
    da_gap, cac_nhom = set(), []
    for nhom in tra_loi.get("groups", []):
        ids = [int(d) for d in nhom if int(d) in bai and int(d) not in da_gap]
        da_gap.update(ids)
        if ids:
            cac_nhom.append(ids)
    for d in bai:
        if d not in da_gap:
            cac_nhom.append([d])
    return cac_nhom


# ---------- 3. Tóm tắt từng sự kiện ----------

def _kiem_tra(ev):
    """Kiểm tra chất lượng tóm tắt, không cần nhãn."""
    s = ev.get("summary", "")
    cac_cau = [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", s) if x.strip()]
    cau_co_trich = [x for x in cac_cau if re.search(r"\[\d+\]", x)]
    so_trich = {int(n) for n in re.findall(r"\[(\d+)\]", s)}
    so_nguon = {x["n"] for x in ev["sources"]}
    return {
        "cau_co_trich_dan": round(len(cau_co_trich) / max(len(cac_cau), 1), 2),
        "trich_dan_hop_le": so_trich <= so_nguon,
        "con_tieng_viet": bool(re.search(r"[À-ỹ]", s + ev.get("headline", ""))),
    }


def _viet_su_kien(ticker, company, nhom, bai, mau):
    """Tóm tắt một sự kiện từ tối đa MAX_SOURCES bài mới nhất trong nhóm."""
    nhom = sorted(nhom, key=lambda d: bai[d]["ngay"])[-MAX_SOURCES:]
    nguon = []
    for n, d in enumerate(nhom, start=1):
        b = bai[d]
        noi_dung = hc.cat_bai_cho_llm(b["noi_dung"], hc.vi_tri_nhac_ten(b["noi_dung"], mau[ticker]), MAX_CHARS, HEAD_CHARS)
        nguon.append(f"[{n}] {b['title']} ({b['ngay']})\n{noi_dung}")

    ev = _hoi_json(EVENT_PROMPT.format(company=company, sources="\n\n".join(nguon)))
    ev["sources"] = [{"n": n, "id": int(d), "title": bai[d]["title"], "date": bai[d]["ngay"], "url": bai[d]["url"]}
                     for n, d in enumerate(nhom, start=1)]
    ev["kiem_tra"] = _kiem_tra(ev)
    return ev


# ---------- 4. Tổng quan và ghép báo cáo ----------

def _them_su_kien(lines, ds_su_kien):
    """Mỗi sự kiện: tiêu đề, ngày, loại, đoạn tóm tắt, các nguồn được trích dẫn."""
    for k, e in enumerate(ds_su_kien, start=1):
        lines.append(f"### {k}. {e.get('headline')}")
        lines.append(f"**Date:** {e.get('date')} | **Category:** {e.get('category')}")
        lines.append("")
        lines.append(e.get("summary", ""))
        lines.append("")
        so_trich = {int(n) for n in re.findall(r"\[(\d+)\]", e.get("summary", ""))}
        for s in e["sources"]:
            if not so_trich or s["n"] in so_trich:   # chỉ liệt kê nguồn được trích dẫn
                lines.append(f"- [{s['n']}] {s['title']} ({s['date']}) {s['url']}")
        lines.append("")


def _ghep_bao_cao(con, run_id, ticker, company, events, so_bai_rui_ro):
    ds = sorted(events, key=lambda e: str(e.get("date", "")), reverse=True)
    items = "\n".join(f"- {e.get('date')} | {e.get('category')} | {e.get('headline')}" for e in ds)
    tong_quan = _hoi_json(OVERVIEW_PROMPT.format(company=company, items=items), max_tokens=3000)

    moc = str(datetime.now().year - RECENT_YEARS)
    gan_day = [e for e in ds if str(e.get("date", "")) >= moc]
    cu = [e for e in ds if str(e.get("date", "")) < moc]
    phieu = con.execute("select n_mention, n_bm25, n_top from screening_runs where run_id = ?", (run_id,)).fetchone()

    lines = [f"# Adverse Media Screening Report: {tong_quan.get('company_name_en', ticker)} ({ticker})", "",
             f"*Draft generated {datetime.now().strftime('%Y-%m-%d')} for analyst review. Run id {run_id}.*", "",
             "## Overview", "", tong_quan.get("overview", ""), "",
             f"## Adverse events in the last {RECENT_YEARS} years ({len(gan_day)})", ""]
    _them_su_kien(lines, gan_day)
    if cu:
        lines += [f"## Earlier events ({len(cu)})", ""]
        _them_su_kien(lines, cu)
    lines += [_phan_phuong_phap(phieu, so_bai_rui_ro, len(ds))]
    return "\n".join(lines), ds


def _phan_phuong_phap(phieu, so_bai_rui_ro, so_su_kien):
    return "\n".join(["## Method", "",
                      f"Articles mentioning the company: {phieu[0]}. Articles with risk keywords: {phieu[1]}. "
                      f"Re-ranked: {phieu[2]}. Read by LLM: top {doc_bai.TOP_K}. Articles confirmed as adverse: "
                      f"{so_bai_rui_ro}, grouped into {so_su_kien} events."])


def _khong_co_su_kien(con, run_id, ticker, ten):
    phieu = con.execute("select n_mention, n_bm25, n_top from screening_runs where run_id = ?", (run_id,)).fetchone()
    lines = [f"# Adverse Media Screening Report: {ten} ({ticker})", "",
             f"*Draft generated {datetime.now().strftime('%Y-%m-%d')} for analyst review. Run id {run_id}.*", "",
             "## Overview", "",
             "No adverse events were confirmed in the articles reviewed.", "",
             _phan_phuong_phap(phieu, 0, 0)]
    return "\n".join(lines)


# ---------- Điểm vào ----------

def tao_bao_cao(con, con_cong_ty, run_id, ticker, bao_cao=lambda s: None):
    """Viết báo cáo cho run_id, lưu vào bảng reports. Trả về số sự kiện."""
    ten = con_cong_ty.execute("select full_name from company_names where ticker = ?", (ticker,)).fetchone()[0]
    company = f"{ten} ({ticker})"
    bai = _bai_rui_ro(con, run_id, ticker)

    if not bai:
        events, report_md = [], _khong_co_su_kien(con, run_id, ticker, ten)
    else:
        mau = prepare.tao_mau(con_cong_ty)
        bao_cao("Gộp các bài cùng một sự kiện")
        cac_nhom = _gop_su_kien(bai, company)

        bao_cao(f"Tóm tắt {len(cac_nhom)} sự kiện")
        events, loi, loi_dau = [], 0, None
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(_viet_su_kien, ticker, company, nhom, bai, mau) for nhom in cac_nhom]
            for fut in as_completed(futures):
                try:
                    events.append(fut.result())
                except Exception as e:
                    loi += 1
                    loi_dau = loi_dau or f"{type(e).__name__}: {str(e)[:150]}"
        if loi:
            # Sự kiện lỗi mà bị bỏ lặng lẽ thì báo cáo thiếu một sự kiện bất lợi mà không ai biết
            raise RuntimeError(f"Không tóm tắt được {loi}/{len(cac_nhom)} sự kiện. Lỗi đầu tiên: {loi_dau}")

        bao_cao("Viết phần tổng quan")
        report_md, events = _ghep_bao_cao(con, run_id, ticker, company, events, len(bai))

    con.execute("insert or replace into reports values (?, ?, ?, ?, ?, ?)",
                (run_id, ticker, len(events), report_md, json.dumps(events, ensure_ascii=False),
                 datetime.now(timezone.utc).isoformat()))
    con.commit()
    return len(events)
