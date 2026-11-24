# Pipeline ER: LLM gắn nhãn + mô hình tính điểm

Sáu notebook chạy theo thứ tự, mỗi notebook đọc kết quả của bước trước trong `pipeline_data/`.

| Notebook | Việc | Đầu ra |
|---|---|---|
| p01_lam_sach | Kiểm tra benchmark, đọc bài, chuẩn hóa văn bản, bỏ cặp hỏng, chia dev/test theo bài | p01_cap.csv, p01_bai.csv |
| p02_thong_ke | Phân bố nhãn theo tập, ticker, nguồn, năm, độ dài bài, loại chuỗi khớp | (chỉ hiển thị) |
| p03_llm_gan_nhan | Cắt đoạn ±10 từ quanh lần nhắc, LLM gắn nhãn 0/1 + độ tự tin | p03_llm.csv |
| p04_feature | Bằng chứng, từ ngữ cảnh, ghép nhãn LLM | p04_feature.csv |
| p05_model | 4 cấu hình mô hình, CV trên dev, chọn ngưỡng, dự đoán test | p05_diem_test.csv, p05_nguong.csv, p05_mo_hinh.joblib |
| p06_so_sanh_test | So LLM với các mô hình trên test, phân tích bất đồng, theo ticker | p06_bang_chi_so.csv, p06_du_doan_test.csv |

`common.py` chứa đường dẫn và các hàm dùng chung (chuẩn hóa văn bản, hồ sơ công ty, tìm lần nhắc, cắt đoạn).

## Chuẩn bị

- Đặt `benchmark_vn100_can_bang.csv`, `common.py` và các notebook cùng một thư mục.
- Sửa đường dẫn `DATA` trong `common.py` nếu khác. Cần `corpus.db` (bảng `articles`), `companies.db` (bảng `vn100_20261106`, `company_names`), và file `.env` có `ANTHROPIC_API_KEY`.
- Thư viện: pandas, scikit-learn, scipy, matplotlib, joblib, anthropic, python-dotenv.

## Chạy

1. p01, p02.
2. p03 với `GIOI_HAN = 20` để thử, đọc vài câu trả lời, rồi đặt `GIOI_HAN = None` và chạy lại (cặp đã có sẽ được bỏ qua).
3. p04, p05, p06.

Đổi prompt thì tăng `PROMPT_VERSION` ở p03 và p04.

## Lưu ý

- Nhãn benchmark do LLM gắn (silver label). Mọi chỉ số là mức đồng thuận với nhãn đó.
- Dev và test chia theo bài, nên cùng một ticker có ở cả hai phía.
