"""Dữ liệu tham chiếu cho Entity Resolution: alias, tên dài hơn, luật loại trừ, hồ sơ công ty."""
import re

import pandas as pd

import config
from text import chuan_hoa

LOAI_HINH = [
    "công ty cổ phần", "công ty tnhh", "một thành viên", "hai thành viên trở lên",
    "tổng công ty", "công ty", "tập đoàn", "chi nhánh", "ctcp", "tnhh", "mtv", "cổ phần", "cp",
]

# Tỉnh mới sau sáp nhập 2025 -> các tên dùng trong bài (gồm tên tỉnh cũ)
TEN_TINH = {
    "Hồ Chí Minh": ["Hồ Chí Minh", "TP.HCM", "TPHCM", "TP HCM", "Sài Gòn", "Bình Dương", "Bà Rịa", "Vũng Tàu"],
    "Hà Nội": ["Hà Nội"],
    "Hải Phòng": ["Hải Phòng", "Hải Dương"],
    "Đà Nẵng": ["Đà Nẵng", "Quảng Nam"],
    "Cần Thơ": ["Cần Thơ", "Sóc Trăng", "Hậu Giang"],
    "Huế": ["Huế"],
    "Tuyên Quang": ["Tuyên Quang", "Hà Giang"],
    "Lào Cai": ["Lào Cai", "Yên Bái"],
    "Thái Nguyên": ["Thái Nguyên", "Bắc Kạn"],
    "Phú Thọ": ["Phú Thọ", "Vĩnh Phúc", "Hòa Bình"],
    "Bắc Ninh": ["Bắc Ninh", "Bắc Giang"],
    "Hưng Yên": ["Hưng Yên", "Thái Bình"],
    "Ninh Bình": ["Ninh Bình", "Hà Nam", "Nam Định"],
    "Quảng Trị": ["Quảng Trị", "Quảng Bình"],
    "Quảng Ngãi": ["Quảng Ngãi", "Kon Tum"],
    "Gia Lai": ["Gia Lai", "Bình Định"],
    "Khánh Hòa": ["Khánh Hòa", "Ninh Thuận"],
    "Lâm Đồng": ["Lâm Đồng", "Đắk Nông", "Bình Thuận"],
    "Đắk Lắk": ["Đắk Lắk", "Phú Yên"],
    "Đồng Nai": ["Đồng Nai", "Bình Phước"],
    "Tây Ninh": ["Tây Ninh", "Long An"],
    "Vĩnh Long": ["Vĩnh Long", "Bến Tre", "Trà Vinh"],
    "Đồng Tháp": ["Đồng Tháp", "Tiền Giang"],
    "Cà Mau": ["Cà Mau", "Bạc Liêu"],
    "An Giang": ["An Giang", "Kiên Giang"],
    "Quảng Ninh": ["Quảng Ninh"],
    "Thanh Hóa": ["Thanh Hóa"],
    "Nghệ An": ["Nghệ An"],
    "Hà Tĩnh": ["Hà Tĩnh"],
}


def tach(cell):
    return [a.strip() for a in str(cell).split(";") if a.strip()]


def ten_loi(ten):
    t = chuan_hoa(ten).lower()
    t = re.sub(r"[-–,.()]", " ", t)
    for lh in LOAI_HINH:
        t = re.sub(rf"(?<!\w){lh}(?!\w)", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def goc_mst(mst):
    return re.sub(r"\D", "", str(mst))[:10]


def tinh_tu_dia_chi(address):
    cuoi = chuan_hoa(address).split(" - ")[-1]
    return re.sub(r"^(Tp\.|T\.)\s*", "", cuoi).strip()


def ten_lanh_dao(key_leaders):
    return [re.sub(r"\(.*?\)", "", x).strip() for x in str(key_leaders).split(";") if x.strip()]


def read_table(con, table):
    return pd.read_sql(f'select * from "{table}"', con).fillna("").replace("NULL", "")


class ErResources:
    def __init__(self, con_companies):
        self.catalog = read_table(con_companies, config.CATALOG_TABLE)
        names = read_table(con_companies, "company_names")
        names = names[names.ticker.isin(self.catalog.ticker)].reset_index(drop=True)
        missing = set(self.catalog.ticker) - set(names.ticker)
        if missing:
            raise ValueError(f"company_names thiếu alias cho: {sorted(missing)}")
        self.names = names.set_index("ticker", drop=False)

        companies = read_table(con_companies, "companies")
        exclusions = pd.read_sql("select * from alias_exclusions where trang_thai = 'duyet'", con_companies).fillna("")

        self.build_aliases()
        self.build_longer_names(companies)
        self.exclusions = {t: [chuan_hoa(p) for p in g.pattern] for t, g in exclusions.groupby("ticker")}
        self.build_profiles(companies)

    def build_aliases(self):
        rows = []
        for _, r in self.names.iterrows():
            for a in tach(r["strong_aliases"]):
                rows.append((r["ticker"], chuan_hoa(a), "strong"))
            for a in tach(r["weak_aliases"]):
                rows.append((r["ticker"], chuan_hoa(a), "ticker" if a == r["ticker"] else "weak"))
            rows.append((r["ticker"], r["ticker"], "ticker"))

        aliases = pd.DataFrame(rows, columns=["ticker", "alias", "loai"]).drop_duplicates()
        # alias tối đa 2 từ thì phân biệt hoa thường
        aliases["phan_biet_hoa"] = aliases["alias"].str.split().str.len() <= 2
        aliases = aliases.sort_values("alias", key=lambda s: s.str.len(), ascending=False)
        self.aliases = aliases

        mau = [re.escape(a) if h else f"(?i:{re.escape(a)})" for a, h in zip(aliases.alias, aliases.phan_biet_hoa)]
        self.alias_re = re.compile(r"(?<!\w)(" + "|".join(mau) + r")(?!\w)")

        self.alias_lookup = {}
        for r in aliases.itertuples():
            key = r.alias if r.phan_biet_hoa else r.alias.lower()
            self.alias_lookup.setdefault(key, []).append((r.ticker, r.loai, r.alias))

    def lookup(self, chuoi):
        return self.alias_lookup.get(chuoi) or self.alias_lookup.get(chuoi.lower(), [])

    def build_longer_names(self, companies):
        # Alias nằm trong tên lõi của pháp nhân khác: lần nhắc có thể thuộc về pháp nhân đó
        companies["ten_loi"] = companies["company_name"].map(ten_loi)
        companies["goc_mst"] = companies["tax_code"].map(goc_mst)

        self.ten_dai_hon = {}
        for r in self.aliases.itertuples():
            if r.loai == "ticker":
                continue
            row = self.names.loc[r.ticker]
            mst_dich = {goc_mst(m) for m in [row["tax_code"]] + tach(row["ma_phu"]) if m}
            a = r.alias.lower()
            khac = companies[
                companies.ten_loi.str.contains(rf"(?<!\w){re.escape(a)}(?!\w)", regex=True)
                & ~companies.goc_mst.isin(mst_dich)
                & (companies.ten_loi != ten_loi(row["full_name"]))
                & (companies.ten_loi.str.len() > len(a))
            ]
            if len(khac):
                self.ten_dai_hon[(r.ticker, r.alias)] = sorted(set(khac.ten_loi), key=len, reverse=True)

    def build_profiles(self, companies):
        legal_rep = dict(zip(companies.tax_code, companies.legal_rep))
        catalog = self.catalog.set_index("ticker")

        self.leaders = {}
        self.provinces = {}
        for t, row in self.names.iterrows():
            ten = ten_lanh_dao(catalog.loc[t, "key_leaders"])
            rep = str(legal_rep.get(row["tax_code"], "")).strip()
            if rep:
                ten.append(rep.title())
            self.leaders[t] = sorted({chuan_hoa(x) for x in ten if len(x.split()) >= 2})

            tinh = tinh_tu_dia_chi(catalog.loc[t, "address"])
            self.provinces[t] = TEN_TINH.get(tinh, [tinh] if tinh else [])
