"""
Dinh nghia dung 1 dang output ma moi lan goi LLM phai tra ve -
de dispatch/luu tru khong can quan tam bai bao tu nguon nao.
"""

from typing import TypedDict, Optional


class AdverseFinding(TypedDict):
    is_match: bool                    # bai nay co dung la ve subject khong
    match_confidence: str             # "high" / "medium" / "low"
    has_adverse_finding: bool
    category: Optional[str]           # "fraud" / "corruption" / "sanctions" / "litigation" / "regulatory" / "other"
    event_date: Optional[str]
    snippet: Optional[str]            # doan trich lam bang chung
    source_url: str
