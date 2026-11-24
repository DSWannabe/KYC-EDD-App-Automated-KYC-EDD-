from typing import Optional

from pydantic import BaseModel


class LookupRequest(BaseModel):
    doan: str                        # đoạn văn người dùng dán
    ten: Optional[str] = None        # tên công ty muốn tra; bỏ trống thì tự tìm trong đoạn


class UngVien(BaseModel):
    ticker: str
    ten_cong_ty: str
    diem: float


class KetQuaTen(BaseModel):
    ten: str
    trang_thai: str                  # duy_nhat | can_xac_nhan | khong_co
    ung_vien: list[UngVien]
    ghi_chu: str = ""


class LookupResponse(BaseModel):
    ket_qua: list[KetQuaTen]
