"""
Parser cho masothue.com - da xac nhan cau truc that qua kiem tra thu cong.

Moi ket qua nam trong 1 <div data-prefetch="/relative-url">:
  <h3><a>TEN CONG TY</a></h3>
  <div><a>MA SO THUE</a> <em><a>NGUOI DAI DIEN</a></em></div>   (rep co the thieu)
  <address>DIA CHI</address>
"""

from urllib.parse import urljoin
from bs4 import BeautifulSoup
from parsers.base import CompanyRecord, empty_record

BASE_URL = "https://masothue.com"


def parse(html: str) -> list[CompanyRecord]:
    soup = BeautifulSoup(html, "lxml")
    records = []

    for container in soup.find_all("div", attrs={"data-prefetch": True}):
        h3 = container.find("h3")
        if not h3:
            continue

        record = empty_record()

        name_link = h3.find("a")
        record["company_name"] = name_link.get_text(strip=True) if name_link else None
        record["detail_url"] = urljoin(BASE_URL, container["data-prefetch"])

        inner_div = h3.find_next_sibling("div")
        if inner_div:
            a_tags = inner_div.find_all("a")
            if len(a_tags) >= 1:
                record["tax_code"] = a_tags[0].get_text(strip=True)
            if len(a_tags) >= 2:
                record["legal_rep"] = a_tags[1].get_text(strip=True)

        address_tag = container.find("address")
        record["address"] = address_tag.get_text(strip=True) if address_tag else None

        records.append(record)

    return records
