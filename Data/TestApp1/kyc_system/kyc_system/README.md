# KYC adverse media screening

Hệ thống gồm hai luồng:

1. **Job nền (`run_background.py`)**: gắn nhãn Entity Resolution cho bài báo mới trong `corpus.db`, rồi tính vector bge-m3 cho các bài có nhắc công ty.
2. **Sàng lọc theo yêu cầu (`run_screen.py`)**: nhận tên, mã chứng khoán hoặc mã số thuế của một công ty, truy xuất bằng chứng, cho LLM xác nhận, viết báo cáo Markdown.

## Luồng dữ liệu

```
crawler -> corpus.db.articles
                |
     run_background.py
        ER: quét alias -> kiểm tra tên dài hơn, luật loại trừ -> f1-f8 + từ ngữ cảnh -> LR -> 1 / 0 / xem
            ghi er_mentions, er_article_company, er_scan
        Vector: bài có cặp 1 hoặc xem -> chunk_vectors
                |
     run_screen.py "<tên | mã CK | MST>"
        resolve.py      -> ticker (từ danh mục VN100)
        retrieval.py    -> các bài ER gắn với công ty -> BM25 v2 + dense -> RRF -> cross-encoder
                           ghi screening_runs, run_results, ce_scores
        llm_read.py     -> LLM đọc top 20 (đọc thêm theo đợt nếu còn nhiều tin xấu), ghi llm_reads, run_llm
        report.py       -> gộp sự kiện, tóm tắt 5W1H có trích dẫn, tổng quan, hồ sơ công ty
                           ghi reports và reports/<mã>_run<số>.md
```

## Các file

| File | Vai trò |
|---|---|
| `config.py` | Đường dẫn DB, model, mọi tham số |
| `schema.sql`, `db.py` | Kết nối DB, tạo bảng của hệ thống trong `corpus.db` |
| `text.py` | Chuẩn hóa tiếng Việt, cắt bài cho LLM |
| `er_resources.py` | Alias, danh bạ tên dài hơn, luật loại trừ, lãnh đạo, tỉnh |
| `er_scan.py` | Quét alias, kiểm tra từng lần nhắc |
| `er_features.py` | f1-f8 và từ ngữ cảnh cho mỗi cặp (bài, ticker) |
| `er_model.py` | Huấn luyện, lưu, dự đoán Logistic Regression |
| `er_pipeline.py` | Chạy ER cho một nhóm bài và ghi DB |
| `embeddings.py` | Vector bge-m3 |
| `retrieval.py` | BM25 v2, dense, RRF, rerank |
| `llm.py`, `prompts.py` | Gọi Claude API, các prompt |
| `llm_read.py` | LLM đọc và xác nhận rủi ro |
| `report.py` | Viết báo cáo |
| `resolve.py` | Tìm công ty từ tên, mã CK, MST |
| `train_er.py` | Script huấn luyện mô hình ER |
| `run_background.py` | Script job nền |
| `run_screen.py` | Script sàng lọc một công ty |

## Cài đặt

```
pip install -r requirements.txt
```

Sửa đường dẫn trong `config.py` nếu khác. File `.env` cần có `ANTHROPIC_API_KEY`.

Trong `companies.db` cần có: `companies`, `company_names` (đủ 9 mã mới), `alias_exclusions`, `VN100(6Nov2026)`.
Thứ tự chuẩn bị: `add_vn100_catalog.py`, `create_alias_exclusions.sql`, `insert_companies_moi.sql`, `insert_company_names_moi.sql`.

Bảng `articles` trong `corpus.db` cần các cột `id, title, cleaned_text, published_at, source_url, content_hash`.

## Chạy

Lần đầu:

```
python train_er.py --v12 articles_labeled_v12_full_relabel.csv --bench benchmark_vn100_can_bang.csv
python run_background.py
```

Mỗi khi crawler thêm bài:

```
python run_background.py
```

Sàng lọc:

```
python run_screen.py "Hòa Phát"
python run_screen.py 0900189284
python run_screen.py HPG --date-from 2021-01-01
```

Nếu tên khớp nhiều công ty, script in danh sách để chọn bằng mã chứng khoán.

Muốn thử trên bản sao DB mà không đụng DB thật:

```
KYC_CORPUS_DB=/path/corpus_test.db KYC_COMPANY_DB=/path/companies_test.db python run_background.py
```

## Khi nào cần chạy lại

| Thay đổi | Việc cần làm |
|---|---|
| Thêm alias, sửa luật loại trừ | Tăng `ER_RULE_VERSION` trong `config.py`, chạy `run_background.py` |
| Thêm nhãn, huấn luyện lại | `train_er.py --version lr_v2`, chạy `run_background.py` (bài gắn bằng mô hình cũ được quét lại) |
| Sửa prompt đọc bài | Tăng `PROMPT_VERSION`; bài sẽ được LLM đọc lại ở lần sàng lọc sau |

Đánh giá mô hình ER trên benchmark (huấn luyện trên v12, bỏ các bài có trong benchmark):

```
python train_er.py --v12 ... --bench ... --eval
```

## Giới hạn hiện tại

- Chỉ sàng lọc được các công ty trong danh mục VN100.
- Báo cáo là bản nháp cho chuyên viên rà soát, không phải kết luận.
- Bảng `article_scan`, `article_company` của prod_01 không còn được dùng; truy xuất đọc kết quả ER từ `er_article_company`.
