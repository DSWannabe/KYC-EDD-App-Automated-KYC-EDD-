"""Gọi LLM. Một hàm duy nhất: llm.hoi(user, system=None, max_tokens=2000) -> text.

KYC_LLM_MODE=real: gọi Claude thật (ANTHROPIC_API_KEY trong backend/.env).
KYC_LLM_MODE=mock: trả JSON giả theo từ khóa, chỉ để kiểm tra luồng chạy.
"""
import json
import re
import threading

from app import config
from app.services.common import ham_chung as hc


class ClaudeLLM:
    def __init__(self):
        import anthropic
        from dotenv import load_dotenv
        load_dotenv(config.ENV_FILE)
        self.client = anthropic.Anthropic()

    def hoi(self, user, system=None, max_tokens=2000):
        kw = {"system": system} if system else {}
        msg = self.client.messages.create(model=config.LLM_MODEL, max_tokens=max_tokens,
                                          messages=[{"role": "user", "content": user}], **kw)
        return "".join(b.text for b in msg.content if b.type == "text")


# ---------- Bản giả ----------

LOAI_THEO_TU = [("thua lỗ", "thua lỗ"), ("báo lỗ", "thua lỗ"), ("từ nhiệm", "thay đổi lãnh đạo"),
                ("miễn nhiệm", "thay đổi lãnh đạo"), ("khởi tố", "khởi tố"), ("bị bắt", "khởi tố")]


class MockLLM:
    """Nhận ra loại prompt qua câu mở đầu, rồi trả JSON đúng định dạng mà code mong đợi."""

    def __init__(self):
        self.tu_rui_ro = set(hc.cum_tu_thanh_token(hc.CUM_TU_RUI_RO))

    def hoi(self, user, system=None, max_tokens=2000):
        if user.startswith("Nhiệm vụ: xác định bài báo có nhắc tới CHÍNH công ty"):
            return json.dumps({"nhan": 1, "tu_tin": 0.8, "ly_do": "[mock] ER xem lại"}, ensure_ascii=False)
        if "Danh sách công ty cần xét:" in user:
            return json.dumps(self._doc_bai(user), ensure_ascii=False)
        if user.startswith("Below is a list of news articles"):
            return json.dumps(self._gop(user))
        if user.startswith("You are a KYC analyst writing one entry"):
            return json.dumps(self._su_kien(user))
        if user.startswith("You are a KYC analyst. Below are"):
            return json.dumps(self._tong_quan(user))
        raise ValueError("MockLLM không nhận ra prompt: " + user[:60])

    def _doc_bai(self, user):
        ticker = re.search(r"Danh sách công ty cần xét:\n- (\w+):", user).group(1)
        tieu_de = re.search(r"Tiêu đề: (.*)", user).group(1)
        noi_dung = user.split("Nội dung:\n", 1)[1].split("\n\nDanh sách công ty cần xét:", 1)[0]

        # câu bằng chứng: câu đầu tiên có từ rủi ro (lấy nguyên văn từ bài)
        for cau in re.split(r"(?<=[.!?])\s+|\n", tieu_de + ". " + noi_dung):
            if self.tu_rui_ro & set(hc.tach_tu_bigram(cau)):
                loai = next((v for k, v in LOAI_THEO_TU if k in cau.lower()), "vi phạm")
                return {"ket_qua": [{"ticker": ticker, "rui_ro": True, "muc_do": "tin_chinh", "loai": loai,
                                     "chu_the": ticker, "bang_chung": cau.strip(), "mo_ta": tieu_de,
                                     "ly_do": "[mock] bài có cụm từ rủi ro"}]}
        return {"ket_qua": [{"ticker": ticker, "rui_ro": False, "muc_do": "khong", "loai": "", "chu_the": "",
                             "bang_chung": "", "mo_ta": "", "ly_do": "[mock] không có cụm từ rủi ro"}]}

    def _gop(self, user):
        # mỗi dòng: id | ngày | loại | mô tả. Gộp các bài cùng loại và cùng tháng.
        nhom = {}
        for dong in re.findall(r"^(\d+) \| (\S+) \| ([^|]*) \|", user, re.M):
            article_id, ngay, loai = dong
            nhom.setdefault((loai.strip(), ngay[:7]), []).append(int(article_id))
        return {"groups": list(nhom.values())}

    def _su_kien(self, user):
        nguon = re.findall(r"^\[(\d+)\] .*\((\d{4}-\d{2}-\d{2})\)$", user, re.M)
        ngay = max(n[1] for n in nguon) if nguon else ""
        tom_tat = " ".join(f"Source {n} reports an adverse event involving the company [{n}]." for n, _ in nguon)
        return {"headline": f"Adverse event reported on {ngay}", "date": ngay,
                "category": "Reputation", "summary": tom_tat}

    def _tong_quan(self, user):
        so_su_kien = len(re.findall(r"^- ", user, re.M))
        return {"company_name_en": "Mock Company",
                "overview": f"[mock] {so_su_kien} adverse events were found. This is a test overview."}


_llm = None
_khoa = threading.Lock()


def lay_llm():
    global _llm
    with _khoa:
        if _llm is None:
            _llm = MockLLM() if config.LLM_MODE == "mock" else ClaudeLLM()
        return _llm
