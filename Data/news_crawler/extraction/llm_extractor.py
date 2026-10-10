"""
Goi LLM voi 1 nhiem vu duy nhat, hep: doc 1 bai da lam sach, tra ve
JSON dung schema AdverseFinding. Khong de LLM tu quyet dinh format
hay tong hop nhieu bai cung luc - moi lan goi chi xu ly 1 bai.
Can bien moi truong ANTHROPIC_API_KEY.
"""

import json
from anthropic import Anthropic

from dotenv import load_dotenv
load_dotenv()

client = Anthropic()

PROMPT_TEMPLATE = """Ban dang phan tich 1 bai bao de phuc vu kiem tra KYC/due diligence.

Subject can kiem tra: {subject_name}

Noi dung bai bao (da lam sach):
---
{article_text}
---

Tra loi CHI BANG JSON, khong them chu nao khac, dung dinh dang:
{{
  "is_match": true/false,
  "match_confidence": "high"/"medium"/"low",
  "has_adverse_finding": true/false,
  "category": "fraud"/"corruption"/"sanctions"/"litigation"/"regulatory"/"other"/null,
  "event_date": "YYYY-MM-DD hoac null neu khong ro",
  "snippet": "doan trich ngan lam bang chung, hoac null"
}}
"""


def extract(subject_name: str, article_text: str, source_url: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(subject_name=subject_name, article_text=article_text)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text.strip()
    raw_text = raw_text.removeprefix("```json").removesuffix("```").strip()

    result = json.loads(raw_text)
    result["source_url"] = source_url
    return result
