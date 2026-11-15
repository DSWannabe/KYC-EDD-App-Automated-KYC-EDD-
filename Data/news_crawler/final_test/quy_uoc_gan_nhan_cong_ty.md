# Quy ước gắn nhãn cong_ty (benchmark ER)

Áp dụng cho cột `cong_ty_moi` trong `articles_labeled_v12_full.csv`.

## Bài toán
Với mỗi cặp (bài báo, ticker trong VN100), quyết định: bài có nhắc trực tiếp tới chính công ty niêm yết mang ticker đó không.
- 1: có → ghi ticker vào `cong_ty_moi`
- 0: không
- u: chưa chắc → ghi vào `cong_ty_can_xem`, chưa đưa vào `cong_ty_moi`
- Bài không có ticker nào đúng → `no`

## Tính là 1
1. Công ty niêm yết được nhắc bằng tên pháp lý, tên viết tắt, thương hiệu hoặc mã cổ phiếu.
2. Chi nhánh, phòng giao dịch, nhà máy, trang trại của chính công ty (vd: Vietcombank chi nhánh Hà Nội, nhà máy Đạm Phú Mỹ).
3. Thương hiệu, chuỗi cửa hàng, sản phẩm do chính công ty sở hữu (vd: FPT Shop → FRT, sữa Vinamilk Flex, Cake by VPBank).
4. Tổ chức nội bộ của công ty (công đoàn, đoàn thanh niên, đảng ủy).
5. Ngân hàng xuất hiện trong danh sách chuyển khoản ủng hộ.
6. Bài chủ yếu nói về công ty con nhưng có nhắc trực tiếp công ty mẹ (vd: "công ty con do Tập đoàn Đất Xanh nắm 84%").
7. Dự án, tòa nhà, sự kiện mang tên công ty, chỉ khi bài đồng thời nhắc trực tiếp tới công ty.

## Tính là 0
1. Công ty con, công ty liên kết, liên doanh, CLB thể thao, khi bài chỉ nhắc tới các đơn vị này (vd: ACBS, VCBS, FPT Telecom, HAGL FC, PV GAS D, Cảng Gemadept Hoa Sen).
2. Tên dự án, khu đô thị, tòa nhà, khu công nghiệp, địa chỉ, giải đấu tài trợ, khi bài không nhắc trực tiếp tới công ty (vd: Vinhomes Grand Park, BT5.5 Viglacera, hầm Đèo Cả, cúp Biwase).
3. Chuỗi chữ trùng tên hoặc ticker nhưng chỉ thứ khác (vd: PTB = Phó trưởng ban, BSI = Brand Strength Index, USD/VND, HSG = học sinh giỏi, STB = Tổng cục Du lịch Singapore, VPI = Viện Dầu khí, Nam Long = tên người, VNM trong mã chuyển khoản).

## Công ty con tự niêm yết trong VN100
Gắn ticker của chính nó, không gắn ticker công ty mẹ.
- Chứng khoán BIDV → BSI = 1, BID = 0
- FPT Retail → FRT = 1, FPT = 0
- Chứng khoán VietinBank → CTS = 1, CTG = 0
- Đất Xanh Services → DXS = 1, DXG = 0 (trừ khi bài nhắc trực tiếp Tập đoàn Đất Xanh)

## Còn để u (chờ quyết)
1. Tên công ty xuất hiện như nơi làm việc của một người (vd: "Phạm Tuyên (Vinamilk)" trong danh sách ủng hộ).
2. Tài sản có từ trước khi công ty thành lập (vd: nhà máy Đạm Cà Mau trước khi có DCM).
