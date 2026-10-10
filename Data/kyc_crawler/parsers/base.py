"""
Khuon chung cho moi parser theo tung site.

Moi site khac nhau ve cau truc HTML, nhung tat ca parser deu phai
nhan vao HTML tho va tra ve CUNG MOT dang du lieu - list cac dict
theo schema ben duoi. Nho vay orchestrator khong can biet parser
nao xu ly the nao ben trong, chi can goi parse(html) va nhan ket qua
dung dang.
"""

from typing import TypedDict, Optional


class CompanyRecord(TypedDict):
    company_name: Optional[str]
    tax_code: Optional[str]
    legal_rep: Optional[str]
    address: Optional[str]
    detail_url: Optional[str]


def empty_record() -> CompanyRecord:
    """Tao 1 record rong, dung khi thieu field thay vi de KeyError."""
    return {
        "company_name": None,
        "tax_code": None,
        "legal_rep": None,
        "address": None,
        "detail_url": None,
    }
