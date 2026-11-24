# Pipeline ER nền: chạy theo luồng của app

Các notebook chạy theo thứ tự, mỗi notebook đọc kết quả của bước trước trong `pipeline_data/`.
Luồng giống app: mô hình LR chấm mọi cặp trước, LLM chỉ xem lại các cặp LR chưa chắc (điểm trong vùng xem lại).

| Notebook | Việc | Đầu ra |
|---|---|---|
| p01_lam_sach | Kiểm tra benchmark, đọc bài, chuẩn hóa văn bản, bỏ cặp hỏng, chia dev/test theo bài | p01_cap.csv, p01_bai.csv |
| p02_thong_ke | Phân bố nhãn theo tập, ticker, nguồn, năm, độ dài bài, loại chuỗi khớp | (chỉ hiển thị) |
| p03_feature | Bằng chứng và từ ngữ cảnh ±5 (không LLM) | p03_feature.csv |
| p04_lr | Tầng 1: LR `lr_ngu_canh` (kèm mốc `lr_bang_chung`), điểm out-of-fold, ngưỡng, vùng xem lại cho 3 mục tiêu | p04_diem.csv, p04_lr.joblib, p04_tham_so.json |
| p05_llm_xem_lai | Tầng 2: LLM hỏi 5 lần cho các cặp test trong vùng xem lại | llm_er.csv |
| p06_danh_gia | Luồng tầng trên test, so với LR một mình (và LLM cho mọi cặp nếu có t01), chi phí, bootstrap | p06_ket_qua.csv, p06_du_doan_test.csv |

Tham chiếu, không bắt buộc:

| Notebook | Việc | Đầu ra |
|---|---|---|
| t01_llm_toan_bo | LLM hỏi mọi cặp dev và test, học `lr_ngu_canh_llm`. Chạy trước p06 nếu muốn so sánh | t01_diem_test.csv, t01_mo_hinh.joblib, t01_feature_llm.csv |
| t02_so_sanh_mo_hinh | So LR, bagging, boosting trên cùng feature, learning curve | t02_diem_test.csv, t02_ket_qua.csv |

`common.py` chứa đường dẫn và các hàm dùng chung: chuẩn hóa văn bản, hồ sơ công ty, tìm lần nhắc, cắt đoạn,
và phần gọi LLM (prompt giống `er/llm_xem_lai.py` của app). Mọi lần hỏi LLM lưu ở `llm_er.csv`, một dòng mỗi lần;
p05 và t01 dùng chung file này nên cặp đã hỏi ở bước trước không bị hỏi lại.
Nếu còn `p03_llm.csv` của pipeline cũ (prompt v2), các lần hỏi cũ được tự chuyển sang `llm_er.csv` ở lần chạy đầu.

## Chuẩn bị

- Đặt `benchmark_vn100_can_bang.csv`, `common.py` và các notebook cùng một thư mục.
- Sửa đường dẫn `DATA` trong `common.py` nếu khác. Cần `corpus.db` (bảng `articles`), `companies.db` (bảng `vn100_20261106`, `company_names`), và file `.env` có `ANTHROPIC_API_KEY`.
- Thư viện: pandas, scikit-learn, scipy, matplotlib, joblib, anthropic, python-dotenv.

## Chạy

1. p01, p02, p03, p04.
2. p05 với `GIOI_HAN = 20` để thử, rồi đặt `GIOI_HAN = None` và chạy lại.
3. (Không bắt buộc) t01 với `GIOI_HAN = None`, t02.
4. p06.

Đổi prompt thì tăng `PROMPT_VERSION` trong `common.py`.

## Tra cứu tự do (q01-q05)

Người dùng dán một đoạn văn kèm tên công ty, hệ thống trả về một công ty duy nhất, tối đa 3 ứng viên cần xác nhận, hoặc "không có trong danh mục". Cần chạy p01, p03, p04 trước (thêm t01 nếu muốn cấu hình có LLM).

| Notebook | Việc | Đầu ra |
|---|---|---|
| q01_tao_truy_van | Biến mỗi cặp benchmark thành một truy vấn: đoạn ±30 từ quanh tên, đáp án là ticker hoặc KHONG_CO | q01_truy_van.csv |
| q02_ung_vien_feature | Sinh ứng viên từ tên (khớp chính xác, khớp một phần, không dấu), tính feature trên đoạn văn | q02_cap.csv |
| q03_llm_cham_diem | LLM chấm từng cặp (đoạn, ứng viên). Mặc định chỉ chấm mẫu 200 truy vấn test (`MAU_TEST`); không bắt buộc | q03_llm.csv |
| q04_mo_hinh | Chấm điểm: dùng lại mô hình p04 (và t01 nếu có), học lại trên đoạn văn, có/không LLM. Điểm dev là out-of-fold | q04_diem.csv, q04_mo_hinh.joblib |
| q05_quyet_dinh_danh_gia | Chọn ngưỡng trên dev, đánh giá trên test, so LLM với mô hình trên mẫu đã chấm, phân tích lỗi, hàm `tra_cuu` để thử | q05_tham_so.csv, q05_bang_chi_so.csv |

`truy_van.py` chứa hàm dùng chung: sinh ứng viên, cắt đoạn, feature của cặp (đoạn, ứng viên), kiểm tra MST, che tên.

## Feature hồ sơ bằng embedding (r01-r02)

So cả đoạn văn với hồ sơ ngữ cảnh của từng ứng viên bằng bge-m3. Chạy sau q04, rồi chạy lại q05.

| Notebook | Việc | Đầu ra |
|---|---|---|
| r01_embedding | Embedding cho đoạn truy vấn, ngữ cảnh dev nhãn 1 của từng công ty, mô tả ngành (đều đã che tên) | r01_emb_*.npy, r01_*.csv |
| r02_feature_ho_so | Hồ sơ = trung bình vector; feature do_giong_ho_so, do_giong_tuong_doi (out-of-fold); mô hình moi_ho_so, ho_so_khong_tfidf | r02_diem.csv, r02_feature.csv, r02_mo_hinh.joblib |

q05 tự đọc `r02_diem.csv` nếu có. Cần `sentence-transformers` và `torch`.

## Lưu ý

- Nhãn benchmark do LLM gắn (silver label). Mọi chỉ số là mức đồng thuận với nhãn đó.
- Dev và test chia theo bài, nên cùng một ticker có ở cả hai phía.
