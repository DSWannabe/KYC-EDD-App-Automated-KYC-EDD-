import sqlite3
from pathlib import Path

NGUON = "/home/anhtupham99/kyc/KYC-EDD-App-Automated-KYC-EDD-/Data/news_crawler/data/corpus.db"
DICH = Path("../data/full/corpus.db")

assert Path(NGUON).is_file(), NGUON
if DICH.exists():
    raise SystemExit(f"{DICH} đã có, xóa đi nếu muốn tạo lại")

con = sqlite3.connect(DICH)
con.execute("attach database ? as nguon", (NGUON,))
# Tạo bảng bằng đúng câu lệnh gốc để giữ khóa chính và kiểu cột
sql_tao = con.execute("select sql from nguon.sqlite_master where type = 'table' and name = 'articles'").fetchone()[0]
con.execute(sql_tao)
con.execute("insert into main.articles select * from nguon.articles")
con.commit()
print("nguồn:", con.execute("select count(*) from nguon.articles").fetchone()[0],
      "| đích:", con.execute("select count(*) from main.articles").fetchone()[0])
con.execute("detach database nguon")
con.close()
