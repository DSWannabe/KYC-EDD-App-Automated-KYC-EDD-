"""
Giai nen zip/rar/7z an toan, CHI lay file PDF (bo qua file khac).
Chan: zip-slip (ten file chua ../), zip bomb (gioi han tong dung luong), file ma hoa.
"""

import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

MAX_TOTAL_BYTES = 3 * 1024**3     # tong dung luong PDF lay ra toi da cho 1 file goc
MAX_NESTED = 2                    # cho phep zip long trong zip toi da 2 cap
ARCHIVE_EXTS = (".zip", ".rar", ".7z")

# Thu lan luot cac cong cu co san tren may (RAR/7z can cong cu ngoai, zip dung thu vien chuan)
TOOLS = [
    ("unrar",  lambda a, o: ["unrar", "x", "-y", "-o+", str(a), f"{o}/"]),
    ("7zz",    lambda a, o: ["7zz", "x", "-y", f"-o{o}", str(a)]),
    ("7z",     lambda a, o: ["7z", "x", "-y", f"-o{o}", str(a)]),
    ("unar",   lambda a, o: ["unar", "-q", "-f", "-o", str(o), str(a)]),
    ("bsdtar", lambda a, o: ["bsdtar", "-xf", str(a), "-C", str(o)]),
]


class NeedsTool(Exception):
    """Thieu cong cu giai nen tren may."""


class ExtractError(Exception):
    """File hong, ma hoa, hoac vuot gioi han an toan."""


def safe_name(name: str) -> str:
    name = Path(name.replace("\\", "/")).name          # bo thu muc -> chan ../
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "file.pdf"


def _unique(dest: Path, name: str) -> Path:
    p, i = dest / name, 1
    while p.exists():
        p = dest / f"{Path(name).stem}_{i}{Path(name).suffix}"
        i += 1
    return p


def _zip_name(info: zipfile.ZipInfo) -> str:
    """Sua ten file tieng Viet bi hong khi zip khong danh dau UTF-8."""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def _copy_limited(src, out, budget: list):
    while chunk := src.read(1024 * 1024):
        budget[0] -= len(chunk)
        if budget[0] < 0:
            raise ExtractError("vuot gioi han dung luong giai nen (nghi zip bomb)")
        out.write(chunk)


def extract_pdfs(archive: Path, dest: Path, _depth: int = 0, _budget: list | None = None) -> list[Path]:
    """Giai nen `archive`, tra ve danh sach file PDF da luu trong `dest`."""
    dest.mkdir(parents=True, exist_ok=True)
    budget = _budget if _budget is not None else [MAX_TOTAL_BYTES]
    kind = archive.suffix.lower()
    if kind == ".zip":
        return _from_zip(archive, dest, _depth, budget)
    if kind in (".rar", ".7z"):
        return _from_external(archive, dest, _depth, budget)
    raise ExtractError(f"khong ho tro dinh dang {kind}")


def _from_zip(archive: Path, dest: Path, depth: int, budget: list) -> list[Path]:
    pdfs = []
    try:
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = _zip_name(info)
                low = name.lower()
                is_pdf, is_arc = low.endswith(".pdf"), low.endswith(ARCHIVE_EXTS)
                if not (is_pdf or (is_arc and depth < MAX_NESTED)):
                    continue
                target = _unique(dest, safe_name(name))
                with z.open(info) as src, open(target, "wb") as out:
                    _copy_limited(src, out, budget)
                if is_pdf:
                    pdfs.append(target)
                else:
                    pdfs += extract_pdfs(target, dest / f"{target.stem}_ext", depth + 1, budget)
                    target.unlink(missing_ok=True)
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as e:
        raise ExtractError(f"khong mo duoc zip: {e}")
    return pdfs


def _from_external(archive: Path, dest: Path, depth: int, budget: list) -> list[Path]:
    tool = next(((n, b) for n, b in TOOLS if shutil.which(n)), None)
    if tool is None:
        raise NeedsTool("thieu cong cu giai nen RAR: sudo apt install unar (hoac unrar / 7zip), "
                        "hoac giai nen tay tren Windows roi dat cac PDF vao thu muc")
    name, build = tool
    pdfs = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        r = subprocess.run(build(archive, tmp), capture_output=True, text=True)
        if r.returncode != 0:
            raise ExtractError(f"{name} loi: {(r.stderr or r.stdout).strip()[-200:]}")
        for f in sorted(tmp.rglob("*")):
            if not f.is_file() or f.is_symlink():
                continue
            low = f.name.lower()
            if low.endswith(".pdf"):
                budget[0] -= f.stat().st_size
                if budget[0] < 0:
                    raise ExtractError("vuot gioi han dung luong giai nen")
                target = _unique(dest, safe_name(f.name))
                shutil.move(str(f), target)
                pdfs.append(target)
            elif low.endswith(ARCHIVE_EXTS) and depth < MAX_NESTED:
                pdfs += extract_pdfs(f, dest / f"{f.stem}_ext", depth + 1, budget)
    return pdfs