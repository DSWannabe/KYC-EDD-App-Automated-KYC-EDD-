import os, requests
from dotenv import load_dotenv
load_dotenv()

from core.query_builder import build_queries
import yaml

config = yaml.safe_load(open("config/tier2_config.yml", encoding="utf-8"))
queries = build_queries("Vingroup", config["query_templates"])

headers = {"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"}

for q in queries:
    resp = requests.post("https://google.serper.dev/search", headers=headers,
                          json={"q": q, "num": 15}, timeout=10)
    print(f"Query: {q}")
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Body: {resp.text}")
    print()