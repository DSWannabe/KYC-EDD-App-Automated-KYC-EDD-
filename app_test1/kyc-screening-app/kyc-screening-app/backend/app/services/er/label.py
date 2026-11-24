"""Gắn nhãn ER bằng mô hình LR cho các cặp (bài, công ty) chưa có nhãn.

Cặp lấy từ article_company_v3 (er/quet.py). Điểm ghi vào er_labels, cột model là phiên bản mô hình.
- Điểm ngoài vùng xem lại: nhãn theo ngưỡng của LR (nguon = lr)
- Điểm trong vùng xem lại: tạm gắn nhãn 1 và chờ LLM xem lại (nguon = cho_llm, xem er/llm_xem_lai.py).
  Tạm gắn 1 vì với KYC, giữ một bài chưa chắc an toàn hơn là bỏ sót tin bất lợi.
Học lại mô hình (scripts/train_er.py) thì phiên bản đổi, các cặp được chấm lại ở lần chạy sau.
"""
import json
from datetime import datetime, timezone

from app import config
from app.services.er.features import dac_trung_bai
from app.services.lookup import text
from app.services.lookup.model import MoHinh

FILE = config.MODELS_DIR / "er_model.json"
SO_CAP_MOI_LAN = 500
SQL_GHI = ("insert or replace into er_labels (article_id, ticker, score, label, model, created_at, score_lr, nguon) "
           "values (?, ?, ?, ?, ?, ?, ?, ?)")


def _doc():
    return json.loads(FILE.read_text(encoding="utf-8"))


def ten_mo_hinh():
    """Phiên bản mô hình đang dùng, ghi trong er_model.json. File cũ chưa có phiên bản thì là 'lr_ngu_canh'."""
    return _doc().get("phien_ban", "lr_ngu_canh")


def vung_xem_lai():
    """(thấp, cao): điểm LR trong khoảng này thì đưa LLM xem lại."""
    d = _doc()
    thap, cao = config.ER_XEM_LAI_MAC_DINH
    return d.get("xem_lai_thap", thap), d.get("xem_lai_cao", cao)


def gan_nhan_moi(con, con_cong_ty, bao_cao=None):
    """Trả về số cặp vừa gắn nhãn."""
    mh = MoHinh(FILE)
    nguong = mh.nguong["nguong"]
    thap, cao = vung_xem_lai()
    ten = ten_mo_hinh()
    ho_so = text.doc_ho_so(con_cong_ty)

    cap = con.execute("""
        select c.article_id, c.ticker from article_company_v3 c
        where not exists (select 1 from er_labels e
                          where e.article_id = c.article_id and e.ticker = c.ticker and e.model = ?)
        order by c.article_id
    """, (ten,)).fetchall()

    bay_gio = datetime.now(timezone.utc).isoformat()
    tam, da_xong = [], 0
    bai_hien_tai, full, do_dai = None, "", 0
    for article_id, ticker in cap:
        if article_id != bai_hien_tai:   # các cặp cùng bài đứng liền nhau, chỉ đọc bài một lần
            tieu_de, noi_dung = con.execute("select title, cleaned_text from articles where id = ?", (article_id,)).fetchone()
            tieu_de = text.chuan_hoa(tieu_de)
            full, do_dai, bai_hien_tai = tieu_de + "\n" + text.chuan_hoa(noi_dung), len(tieu_de), article_id
        if ticker not in ho_so.index:
            continue
        d = dac_trung_bai(full, do_dai, ticker, ho_so.loc[ticker])
        diem = round(mh.diem(d), 4) if d else 0.0   # quét và tính feature cùng dùng lan_nhac nên d gần như luôn có

        if d and thap <= diem <= cao:
            nhan, nguon = 1, "cho_llm"
        else:
            nhan, nguon = int(bool(d) and diem >= nguong), "lr"
        tam.append((int(article_id), ticker, diem, nhan, ten, bay_gio, diem, nguon))

        if len(tam) >= SO_CAP_MOI_LAN:
            con.executemany(SQL_GHI, tam)
            con.commit()
            da_xong += len(tam)
            tam = []
            if bao_cao:
                bao_cao(f"Gắn nhãn ER {da_xong}/{len(cap)} cặp")
    if tam:
        con.executemany(SQL_GHI, tam)
        con.commit()
        da_xong += len(tam)
    return da_xong
