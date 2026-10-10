"""
Nap bao cao thuong nien da tai ve (pdf / zip / rar) vao DB: giai nen, luu PDF, tach text tung trang.
Chay lai bao nhieu lan cung an toan: file da nap (cung sha256) se duoc bo qua.

    python ingest_reports.py "/mnt/d/.../Bao Cao Thuong Nien VN100" --dry-run
    python ingest_reports.py "/mnt/d/.../Bao Cao Thuong Nien VN100"
    python ingest_reports.py "<thu muc>" --only ACB BCM
"""

import argparse
import hashlib
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path

import pymupdf

import archives
import reports_db as db

STORE_DIR = Path(__file__).parent / "data" / "reports"
SUPPORTED = ("pdf", "zip", "rar", "7z")
# Bao_cao_thuong_nien_nam_2025_ACB.pdf   hoac   ACB_annual_2025.pdf (do download_reports.py tao ra)
NAME_PATTERNS = [
    (re.compile(r"^Bao_cao_thuong_nien_nam_(\d{4})_([A-Za-z0-9]+)\.(\w+)$", re.I), "year_ticker"),
    (re.compile(r"^([A-Za-z0-9]+)_annual_(\d{4})\.(\w+)$", re.I), "ticker_year"),
]
DONE = {"ok", "empty"}        # trang thai da xong; needs_tool/error se duoc thu lai lan sau
MIN_PAGE_CHARS = 20           # trang it hon 20 ky tu coi nhu khong co text (anh quet, trang bia)
DOC_TYPE_KEYWORDS = [         # doan loai tai lieu tu ten file (khong dau, chu thuong)
    ("financial_statements", ("tai chinh", "bctc", "financial")),
    ("governance", ("quan tri", "governance")),
    ("sustainability", ("ben vung", "sustainab", "esg")),
    ("annual_report", ("thuong nien", "annual", "bctn")),
]


def parse_name(name: str):
    for pattern, order in NAME_PATTERNS:
        m = pattern.match(name)
        if m and m.group(3).lower() in SUPPORTED:
            a, b, ext = m.groups()
            year, ticker = (a, b) if order == "year_ticker" else (b, a)
            return ticker.upper(), int(year), ext.lower()
    return None


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c))


def guess_doc_type(name: str, default: str) -> str:
    flat = strip_accents(name).replace("_", " ").replace("-", " ")
    return next((t for t, kws in DOC_TYPE_KEYWORDS if any(k in flat for k in kws)), default)


def pdf_pages(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("PDF co mat khau")
        return [unicodedata.normalize("NFC", p.get_text("text")).replace("\x00", "") for p in doc]


def text_stats(pages: list[str]):
    chars = sum(len(t) for t in pages)
    junk = sum(1 for t in pages for c in t if c == "\ufffd" or "\ue000" <= c <= "\uf8ff")
    text_pages = sum(1 for t in pages if len(t.strip()) >= MIN_PAGE_CHARS)
    return text_pages, chars, (junk / chars if chars else 0.0)


def ingest_pdf(conn, file_id, pdf: Path, ticker, year, default_type: str) -> dict:
    sha = sha256_of(pdf)
    existing = db.doc_id_by_sha(conn, sha)
    if existing:
        return {"name": pdf.name, "status": "duplicate", "note": f"trung doc #{existing}"}

    dest = STORE_DIR / ticker / str(year) / f"{sha[:8]}_{archives.safe_name(pdf.name)}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(pdf, dest)

    doc = dict(file_id=file_id, ticker=ticker, fiscal_year=year,
               doc_type=guess_doc_type(pdf.name, default_type),
               relative_name=pdf.name, stored_path=str(dest.relative_to(STORE_DIR)),
               sha256=sha, size_bytes=pdf.stat().st_size,
               page_count=0, text_pages=0, text_chars=0, status="ok", note="")
    pages = []
    try:
        pages = pdf_pages(dest)
        text_pages, chars, junk = text_stats(pages)
        doc.update(page_count=len(pages), text_pages=text_pages, text_chars=chars)
        if not pages:
            doc.update(status="error", note="PDF khong co trang nao")
        elif text_pages / len(pages) < 0.5:
            doc.update(status="scanned_needs_ocr", note=f"chi {text_pages}/{len(pages)} trang co text")
        elif junk > 0.01:
            doc.update(status="garbled_text", note=f"{junk:.1%} ky tu loi/khong anh xa duoc")
    except Exception as e:
        doc.update(status="error", note=repr(e)[:200])

    doc_id = db.insert_doc(conn, **doc)
    db.insert_pages(conn, doc_id, [(i + 1, t) for i, t in enumerate(pages) if len(t.strip()) >= MIN_PAGE_CHARS])
    return {"name": pdf.name, "status": doc["status"], "note": doc["note"],
            "pages": doc["page_count"], "text_pages": doc["text_pages"]}


def ingest_file(conn, path: Path, ticker: str, year: int, ftype: str) -> dict:
    sha = sha256_of(path)
    prev = db.find_file(conn, sha)
    if prev and prev["status"] in DONE:
        note = f"da nap truoc do ({prev['ticker']}: {prev['original_name']})"
        if prev["ticker"] != ticker:
            note += f" - CUNG NOI DUNG voi file cua ma {prev['ticker']}, kiem tra xem co tai nham file khong"
        return {"status": "skipped", "note": note, "docs": []}
    if prev:
        db.delete_file(conn, prev["id"])      # needs_tool / error -> nap lai tu dau

    status, note, pdfs, docs = "ok", "", [], []
    with tempfile.TemporaryDirectory() as tmp:
        try:
            pdfs = [path] if ftype == "pdf" else archives.extract_pdfs(path, Path(tmp))
        except archives.NeedsTool as e:
            status, note = "needs_tool", str(e)
        except archives.ExtractError as e:
            status, note = "error", str(e)
        if status == "ok" and not pdfs:
            status, note = "empty", "khong co file PDF ben trong"

        file_id = db.insert_file(conn, ticker=ticker, fiscal_year=year, original_name=path.name,
                                 file_type=ftype, size_bytes=path.stat().st_size,
                                 sha256=sha, status=status, note=note)
        # file goc la PDF, hoac archive chi co dung 1 PDF -> coi la bao cao thuong nien
        default_type = "annual_report" if (ftype == "pdf" or len(pdfs) == 1) else "unknown"
        for pdf in pdfs:
            docs.append(ingest_pdf(conn, file_id, pdf, ticker, year, default_type))
    conn.commit()
    return {"status": status, "note": note, "docs": docs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--only", nargs="+", help="chi nap cac ma chung khoan nay")
    ap.add_argument("--db", default=None)
    ap.add_argument("--dry-run", action="store_true", help="chi liet ke, khong giai nen, khong ghi DB")
    args = ap.parse_args()

    only = {t.upper() for t in args.only} if args.only else None
    entries, ignored = [], []
    for p in sorted(args.folder.iterdir()):
        if not p.is_file():
            continue
        parsed = parse_name(p.name)
        if parsed is None:
            ignored.append(p.name)
        elif only is None or parsed[0] in only:
            entries.append((p, *parsed))

    for name in ignored:
        print(f"  [bo qua] ten file khong theo mau: {name}")

    if args.dry_run:
        for p, ticker, year, ftype in entries:
            print(f"  {ticker:<6} {year}  {ftype:<4} {p.stat().st_size / 1e6:>8.1f} MB  {p.name}")
        print(f"{len(entries)} file se duoc nap")
        return

    conn = db.connect(args.db)
    problems, counts = [], {}
    for p, ticker, year, ftype in entries:
        try:
            r = ingest_file(conn, p, ticker, year, ftype)
        except Exception as e:
            conn.rollback()
            r = {"status": "error", "note": repr(e)[:200], "docs": []}
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        docs = " | ".join(f"{d['name']}: {d['status']}" + (f" ({d['pages']}tr, {d['text_pages']} co text)" if "pages" in d else "")
                          for d in r["docs"])
        print(f"[{ticker}] {ftype} -> {r['status']} {r['note']} {docs}")
        if r["status"] in ("needs_tool", "error", "empty"):
            problems.append(f"{p.name}: {r['status']} {r['note']}")
        problems += [f"{p.name} / {d['name']}: {d['status']} {d['note']}" for d in r["docs"]
                     if d["status"] in ("scanned_needs_ocr", "garbled_text", "error")]

    print("\n[TONG] " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if problems:
        print("\nCan xu ly:")
        for line in problems:
            print("  -", line)
    conn.close()


if __name__ == "__main__":
    main()