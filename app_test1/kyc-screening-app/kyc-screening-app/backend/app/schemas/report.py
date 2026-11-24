from typing import List

from pydantic import BaseModel


class BaoCao(BaseModel):
    run_id: int
    ticker: str
    n_events: int
    report_md: str        # báo cáo Markdown, ReportPage hiển thị trực tiếp
    events: List[dict]    # các sự kiện kèm nguồn, dùng khi cần hiển thị riêng từng sự kiện
    created_at: str
