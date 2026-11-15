import sqlite3
import pandas as pd

DB_PATH = "/home/anhtupham99/kyc/KYC-EDD-App-Automated-KYC-EDD-/Data/kyc_crawler/data/companies.db"
CSV_PATH = "/home/anhtupham99/kyc/KYC-EDD-App-Automated-KYC-EDD-/Data/news_crawler/ER/vn100_catalog.csv"
TABLE = "VN100(6Nov2026)"

catalog = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
print(len(catalog), "dòng,", list(catalog.columns))

con = sqlite3.connect(DB_PATH)
con.execute(f'''
CREATE TABLE IF NOT EXISTS "{TABLE}" (
    ticker            TEXT PRIMARY KEY,
    tax_id            TEXT,
    company_name      TEXT,
    short_name        TEXT,
    key_leaders       TEXT,
    address           TEXT,
    industry          TEXT,
    industry_keywords TEXT,
    website           TEXT
)
''')

con.executemany(
    f'INSERT OR REPLACE INTO "{TABLE}" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
    catalog[["ticker", "tax_id", "company_name", "short_name", "key_leaders",
             "address", "industry", "industry_keywords", "website"]].values.tolist(),
)
con.commit()

print(con.execute(f'SELECT COUNT(*) FROM "{TABLE}"').fetchone()[0], "dòng trong bảng")
print(con.execute(f'SELECT ticker, tax_id, short_name FROM "{TABLE}" LIMIT 3').fetchall())
con.close()
