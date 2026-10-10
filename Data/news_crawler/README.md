# Jobs/crawl_daily.py

Job crawl hang ngay: RSS/sitemap -> URL moi -> bo URL da co trong DB -> tai + lam sach
-> bo bai trung noi dung -> luu. Chay lai bao nhieu lan cung an toan (idempotent).

    python -m jobs.crawl_daily                    # tat ca nguon enabled
    python -m jobs.crawl_daily --only vnexpress   # 1 nguon
    python -m jobs.crawl_daily --discover-only    # chi kiem tra feed, khong tai bai, khong ghi DB
    python -m jobs.crawl_daily --limit 20         # toi da 20 bai moi tai ve / nguon (de thu)

# Jobs/backfill_search.py

Tim bai CU qua trang tim kiem noi bo cua cac bao (khoi `search:` trong config/news_sources.yml),
dua URL tim duoc vao cung luong tai -> lam sach -> chong trung -> luu voi crawl_daily.
Truy van da tim xong duoc ghi lai, chay lai se bo qua (dung --force de tim lai).

    python -m jobs.backfill_search --site vnexpress --query vingroup --pages 3 --dry-run
    python -m jobs.backfill_search --site all --queries-file queries.txt --pages 3
    python -m jobs.backfill_search --site tuoitre dantri --query "Vingroup" --from-ts 1577836800 --to-ts 1609459199

# kyc_crawler/orhestratory.py

Crawl theo trang mã số thuế 

