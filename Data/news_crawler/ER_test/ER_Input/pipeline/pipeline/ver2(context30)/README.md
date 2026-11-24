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

## Tra cứu tự do (q01-q05)

Người dùng dán một đoạn văn kèm tên công ty, hệ thống trả về một công ty duy nhất, tối đa 3 ứng viên cần xác nhận, hoặc "không có trong danh mục". Cần chạy p01, p04, p05 trước.

| Notebook | Việc | Đầu ra |
|---|---|---|
| q01_tao_truy_van | Biến mỗi cặp benchmark thành một truy vấn: đoạn ±30 từ quanh tên, đáp án là ticker hoặc KHONG_CO | q01_truy_van.csv |
| q02_ung_vien_feature | Sinh ứng viên từ tên (khớp chính xác, khớp một phần, không dấu), tính feature trên đoạn văn | q02_cap.csv |
| q03_llm_cham_diem | LLM chấm từng cặp (đoạn, ứng viên). Mặc định chỉ chấm mẫu 200 truy vấn test (`MAU_TEST`); không bắt buộc | q03_llm.csv |
| q04_mo_hinh | Chấm điểm: dùng lại mô hình p05, học lại trên đoạn văn, có/không LLM. Điểm dev là out-of-fold | q04_diem.csv, q04_mo_hinh.joblib |
| q05_quyet_dinh_danh_gia | Chọn ngưỡng trên dev, đánh giá trên test, so LLM với mô hình trên mẫu đã chấm, phân tích lỗi, hàm `tra_cuu` để thử | q05_tham_so.csv, q05_bang_chi_so.csv |

`truy_van.py` chứa hàm dùng chung: sinh ứng viên, cắt đoạn, feature của cặp (đoạn, ứng viên), kiểm tra MST.

## Lưu ý

- Nhãn benchmark do LLM gắn (silver label). Mọi chỉ số là mức đồng thuận với nhãn đó.
- Dev và test chia theo bài, nên cùng một ticker có ở cả hai phía.
