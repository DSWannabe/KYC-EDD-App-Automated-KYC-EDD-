"""Gọi Claude API, lấy đối tượng JSON trong câu trả lời."""
import json
import re
import time

import config

_client = None


def client():
    global _client
    if _client is None:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv(config.ENV_FILE)
        _client = anthropic.Anthropic()
    return _client


def ask_json(prompt, max_tokens=2000, retries=3):
    for attempt in range(retries):
        try:
            msg = client().messages.create(
                model=config.LLM_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in msg.content if b.type == "text")
            return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
