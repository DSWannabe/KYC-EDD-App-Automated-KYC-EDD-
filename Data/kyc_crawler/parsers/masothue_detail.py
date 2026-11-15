"""
Parse trang chi tiet cong ty tren masothue.com.
Moi dong trong bang .table-taxinfo la cap (nhan, gia tri). Ta tra nhan -> cot.
Muc nao khong co tren trang thi gia tri la None (de trong).
"""

from bs4 import BeautifulSoup

# Nhan hien tren trang -> ten cot trong companies.db
LABELS = {
    "Tên quốc tế": "international_name",
    "Ngày hoạt động": "operation_date",
    "Tình trạng": "status",
    "Loại hình DN": "legal_type",
    "Điện thoại": "phone",
    "Ngành nghề chính": "industry",
}


def _value_text(td):
    """Lay chu cua o gia tri, bo cac nut bam (vd 'An so dien thoai')."""
    for button in td.find_all("button"):
        button.decompose()
    return " ".join(td.get_text(" ", strip=True).split()) or None


def parse_detail(html: str) -> dict:
    result = {col: None for col in LABELS.values()}
    table = BeautifulSoup(html, "lxml").find("table", class_="table-taxinfo")
    if table is None:
        return result

    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) != 2:
            continue
        label = tds[0].get_text(" ", strip=True)
        col = LABELS.get(label)
        if col:
            result[col] = _value_text(tds[1])
    return result
