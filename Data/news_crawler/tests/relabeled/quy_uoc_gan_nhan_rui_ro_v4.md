---
phien_ban: v4
ngay: 2026-11-12
nhiem_vu: Gắn nhãn rủi ro cho từng công ty VN100 được nhắc trong một bài báo
vi_du_lay_tu: chỉ tập dev (giữ nguyên các ví dụ của v3)
f1_tren_dev: chưa đo
thay_doi_so_voi_v3: >
  Ghi thành quy tắc các quyết định đã áp dụng khi gắn nhãn lại 6.729 cặp bài–mã VN100:
  danh sách khớp nhầm tên, công ty con/đơn vị trực thuộc, chi tiết thay đổi lãnh đạo,
  công ty chứng khoán, dự báo và kế hoạch lợi nhuận, nợ, bài tổng hợp nhiều công ty,
  các trường hợp phải ghi khong_ro, và danh sách giá trị chuẩn cho trường loai.
---

# Nhiệm vụ

Bạn đọc một bài báo tiếng Việt và một danh sách công ty niêm yết được nhắc trong bài. Với từng công ty, kết luận công ty đó có gặp rủi ro (sự kiện bất lợi) trong bài này hay không. Kết quả dùng cho sàng lọc thẩm định doanh nghiệp (KYC).

# Thứ tự xét cho mỗi công ty

1. Công ty có thật sự được nhắc trong bài không? Áp dụng mục "Khớp nhầm tên".
2. Công ty có phải chủ thể của sự kiện bất lợi không? Áp dụng mục "Xác định chủ thể".
3. Sự kiện có thuộc mục "Tính là rủi ro" không? Nếu rơi vào mục "Không tính là rủi ro" thì kết luận không có rủi ro.
4. Sự kiện là tin chính của bài hay chỉ được nhắc qua? Áp dụng mục "Tin chính hay chỉ nhắc qua".

Công ty chỉ có rủi ro khi qua được cả 4 bước. Nếu bước nào không kết luận được, áp dụng mục "Khi không chắc chắn".

# Khớp nhầm tên

Nếu tên hoặc mã chỉ trùng với tên người, địa danh, từ viết tắt hay một công ty khác thì công ty không được nhắc thật. Kết luận `muc_do: "khong"`, ghi rõ trong `ly_do` là khớp nhầm. Các trường hợp hay gặp:

- "Văn Phú", "Vũ Phát Đạt", "Hoàng Huy" là tên người. "Nguyễn Văn Phú" không phải Văn Phú - Invest (VPI); "Hoàng Huy Hiển" không phải Hoàng Huy (TCH).
- "Đèo Cả" là địa danh (đèo, đường sắt qua đèo, sạt lở đèo), không phải Đèo Cả (HHV), trừ khi bài nói về công ty hoặc dự án do công ty làm chủ đầu tư.
- "KDC" là khu dân cư. "VND" là đồng Việt Nam. "HSG" là học sinh giỏi hoặc chụp tử cung - vòi trứng. "VCK" là vòng chung kết. "Nhơn Trạch 2" có thể là khu công nghiệp.
- "BSI" có thể là Brand Strength Index, British Standards Institution hoặc chứng khoán khác. "SIP" có thể là Sterilization In Place. "PVD" có thể là công nghệ phủ chân không. "HT1" có thể là giàn khai thác Hải Thạch. "FTS", "CTS", "BMP", "NAB" có thể là mã động cơ, kênh YouTube, xe chiến đấu, National Australia Bank.
- "Phát Đạt" có thể là cơ sở đóng vỏ lãi, không phải Phát Đạt (PDR). "VPL-S3" là tên giải bóng đá, không phải Vinpearl. "VHC" có thể là nhà bán lẻ điện máy.
- "Sở Giao dịch Chứng khoán TP.HCM (HOSE)" không phải Chứng khoán HSC (HCM). Mã HCM chỉ khớp khi bài nói "HSC", "Chứng khoán HSC", "Chứng khoán TP.HCM", "Chứng khoán Thành phố Hồ Chí Minh" hoặc "mã/cổ phiếu HCM".
- Kho xăng dầu "Hoàng Huy" trong vụ Thiên Minh Đức là doanh nghiệp khác, không phải TCH.

# Xác định chủ thể

- Công ty con có mã chứng khoán riêng: sự kiện tính cho chính công ty con, không tính cho công ty mẹ.
- Chi nhánh, cửa hàng, đơn vị thành viên, công ty con chưa niêm yết (kể cả khi tên khác công ty mẹ): sự kiện tính cho công ty mẹ.
- Nhân viên hoặc lãnh đạo của các đơn vị này vi phạm trong công việc: tính cho công ty mẹ, kể cả khi công ty nói đó là hành vi cá nhân. Ví dụ kế toán cửa hàng tham ô, trưởng nhóm kho quỹ lấy tài sản của ngân hàng.
- Công ty mẹ chưa niêm yết gặp sự kiện: không tính cho công ty con niêm yết chỉ được nhắc là "thành viên của tập đoàn".
- Mảng kinh doanh, thương hiệu, câu lạc bộ thể thao (HAGL FC, CLB quần vợt Becamex, các đội bóng chuyền mang tên ngân hàng) không phải là đơn vị trực thuộc theo nghĩa trên: không tính.
- Công ty chỉ là đối tác, bên cho vay, bên bán tài sản cho người khác, nơi mở tài khoản, cổ đông của công ty gặp sự kiện: không tính.

Các công ty con có mã riêng hay bị nhắc cùng công ty mẹ:

- Vincom Retail (VRE), Vinhomes (VHM), Vinpearl (VPL): không tính cho Vingroup (VIC).
- Chứng khoán BIDV (BSI): không tính cho BIDV (BID).
- Chứng khoán VietinBank (CTS): không tính cho VietinBank (CTG).
- FPT Retail (FRT), Chứng khoán FPT (FTS): không tính cho FPT (FPT).
- Đất Xanh Services (DXS): không tính cho Đất Xanh (DXG).
- Becamex IJC (IJC): không tính cho Becamex IDC (BCM).
- Masan Consumer (MCH), Masan High-Tech Materials (MSR): không tính cho Masan (MSN).
- Chứng khoán Kỹ Thương (TCX): không tính cho Techcombank (TCB).
- Chứng khoán VPBank (VPX): không tính cho VPBank (VPB).
- PV GAS D (PGD): không tính cho PV GAS (GAS).
- Viglacera Đông Triều (DTC): không tính cho Viglacera (VGC).
- Vinaconex 6, Vinaconex 25 và các công ty Vinaconex có mã riêng: không tính cho Vinaconex (VCG).

Các đơn vị chưa niêm yết tính cho công ty mẹ:

- Dabaco Thanh Hóa, Dabaco Hòa Bình → DBC. Công ty con của Biwase → BWE. P-Lab → PNJ. FPT Shop, Long Châu → FRT. Bách Hóa Xanh, Điện Máy Xanh → MWG. Cửa hàng xăng dầu, công ty xăng dầu khu vực Petrolimex → PLX. Công ty vận tải biển Gemadept → GMD. Chi nhánh Viettel Post → VTP. Công ty cao su thành viên Tập đoàn Cao su → GVR.

# Tính là rủi ro

- Vi phạm, bị xử phạt, truy thu thuế, thanh tra, điều tra, khởi tố, lãnh đạo bị bắt (kể cả cựu lãnh đạo). Kể cả vụ việc đang điều tra, chưa có kết luận, và vi phạm đã được khắc phục nhưng tiêu đề vẫn nêu sai phạm.
- Cổ phiếu bị đưa vào diện cảnh báo hoặc diện kiểm soát, báo cáo tài chính có ý kiến ngoại trừ.
- Là nạn nhân: bị cướp, bị mạo danh (trang web giả, hàng nhái thương hiệu), bị lừa đảo, bị tấn công mạng (kể cả khi không tổn thất), bị thiệt hại do mua trái phiếu.
- Tranh chấp, kiện tụng, khiếu nại kết quả đấu thầu, kể cả khi thắng kiện hoặc vụ án bị đình chỉ, hoãn xử.
- Tin đồn ảnh hưởng tới công ty, kể cả khi công ty lên tiếng bác bỏ. Khiếu nại của khách hàng (tố tráo hàng, làm mất hàng, sản phẩm lỗi).
- Thua lỗ, lợi nhuận giảm (kể cả lũy kế giảm dù quý gần nhất tăng), kế hoạch lợi nhuận giảm, nợ xấu, chậm trả nợ, không chia được cổ tức hoặc khất cổ tức.
- Lãnh đạo hoặc cổ đông lớn bị công ty chứng khoán bán giải chấp cổ phiếu của công ty.
- Kiểm toán điều chỉnh giảm, dự án đình trệ, bỏ hoang hoặc chậm tiến độ (kể cả nằm trong danh sách dự án chậm triển khai do cơ quan nhà nước công bố), sự cố, tai nạn do tàu xe của công ty gây ra, thiệt hại do thiên tai.
- Thay đổi lãnh đạo cấp cao: xem mục "Thay đổi lãnh đạo".

# Thay đổi lãnh đạo

Tính là rủi ro khi có bổ nhiệm, bầu mới, miễn nhiệm, từ nhiệm, từ chức, bị đình chỉ, bị sa thải hoặc qua đời ở các chức danh:

- Chủ tịch HĐQT, phó chủ tịch HĐQT, thành viên HĐQT (kể cả thành viên mới được bầu hoặc bầu bổ sung).
- Tổng giám đốc (kể cả quyền tổng giám đốc, CEO), phó tổng giám đốc.
- Trưởng ban kiểm soát, kế toán trưởng.
- Phó tổng giám đốc không được bổ nhiệm lại cũng tính.

Không tính:

- Tái bổ nhiệm, gia hạn nhiệm kỳ cho cùng người ở cùng chức danh.
- Ứng viên, người được đề cử HĐQT nhưng bài chưa nói đã được bầu.
- Thành viên ban kiểm soát (không phải trưởng ban), trưởng tiểu ban, giám đốc chức năng (nhân sự, marketing...).
- Lãnh đạo công ty dự định chuyển giao trong tương lai, chưa có quyết định.
- Lãnh đạo của công ty này giữ hoặc rời chức danh ở một công ty khác.
- Lý lịch, nơi làm việc cũ của lãnh đạo mới: công ty cũ không có rủi ro.

# Không tính là rủi ro

- Danh sách ủng hộ từ thiện (ngân hàng chỉ xuất hiện như kênh chuyển khoản), quảng cáo, giải thưởng, hợp tác, ra mắt sản phẩm, khuyến mãi, tài trợ.
- Biến động chung của thị trường chứng khoán: giá cổ phiếu tăng giảm, giảm sàn nhiều phiên, khối ngoại bán ròng, bị cắt khỏi rổ chỉ số, sở giao dịch yêu cầu giải trình biến động giá.
- Biểu lãi suất, ngân hàng tăng hoặc giảm lãi suất.
- Chỉ doanh thu giảm, lợi nhuận không giảm hoặc tăng.
- Chưa đạt kế hoạch nhưng lợi nhuận vẫn tăng.
- Thay đổi sở hữu, thoái vốn, mua lại công ty, cổ đông hoặc lãnh đạo tự mua bán cổ phiếu, phát hành cổ phiếu, trái phiếu.
- Nợ vay, nợ phải trả tăng, "nỗi lo nợ vay", tồn kho tăng, khi bài không nói nợ xấu hay chậm trả nợ.
- Tái cấu trúc: đóng chi nhánh, giải thể công ty con không hoạt động, cắt giảm nhân sự, bán tài sản.
- Hoãn đại hội cổ đông theo chỉ đạo phòng dịch. Nhân viên nhiễm bệnh và đã được cách ly.
- Ngân hàng bán tài sản thế chấp hoặc bán khoản nợ của khách vay, hoặc chỉ là bên cho vay, bên nhận thế chấp.
- Chỉ phát cảnh báo cho khách hàng mà bản thân không bị mạo danh.
- Công ty chứng khoán chỉ đưa nhận định, dự báo, khuyến nghị về công ty khác hoặc thị trường.
- Công ty chứng khoán là bên thực hiện bán giải chấp cổ phiếu của người khác.
- Công ty khác đầu tư vào cổ phiếu của công ty này bị lỗ.
- Quỹ đầu tư lãi thấp hơn vì không mua cổ phiếu của công ty này.
- Công ty chỉ được nhắc qua, còn sự kiện thuộc về công ty khác.

# Khi hai quy tắc chồng nhau

- Bán giải chấp là bị ép bán, nên tính là rủi ro cho công ty có cổ phiếu bị bán. Cổ đông tự mua hoặc tự bán thì không tính.
- Lợi nhuận giảm thì tính, kể cả khi doanh thu tăng. Chỉ doanh thu giảm thì không tính.
- Thắng kiện vẫn tính, vì công ty vẫn là một bên trong vụ kiện.
- Tin đồn bị bác bỏ vẫn tính, vì tin đồn đã ảnh hưởng tới công ty.
- Bài vừa có thay đổi lãnh đạo vừa có kết quả kinh doanh tích cực: tính theo thay đổi lãnh đạo.

# Kế hoạch và dự báo lợi nhuận

- Kế hoạch lợi nhuận do chính công ty đặt ra thấp hơn năm trước, có số liệu hoặc so sánh rõ, nằm ở tiêu đề, đoạn mở đầu hoặc trong ít nhất 2 câu: tính, `loai: "kế hoạch lợi nhuận giảm"`.
- Kế hoạch được mô tả là "thận trọng" nhưng không nêu so sánh giảm: `khong_ro`.
- Dự báo lợi nhuận giảm do công ty chứng khoán hoặc chuyên gia đưa ra, không phải số liệu thực tế: `khong_ro` nếu ở tiêu đề hoặc đoạn mở đầu; `nhac_qua` nếu chỉ một câu.

# Bài tổng hợp nhiều công ty

Bài liệt kê nhiều công ty (bản tin thị trường, xếp hạng, kết quả kinh doanh của cả ngành):

- Tiêu đề hoặc đoạn mở đầu nêu sự kiện bất lợi chung (ví dụ "lợi nhuận nhiều ngân hàng đi lùi", "chỉ tiêu lợi nhuận sụt giảm mạnh"), và công ty có số liệu riêng xác nhận sự kiện đó: tính là tin chính cho công ty ấy.
- Công ty có ít nhất 2 câu kèm chi tiết về sự kiện bất lợi của chính nó: tính là tin chính.
- Công ty chỉ có một câu: `nhac_qua`.
- Công ty chỉ được nhắc trong câu liệt kê giá cổ phiếu, xếp hạng, danh sách tài trợ: `khong`.

# Tin chính hay chỉ nhắc qua

Sự kiện bất lợi là **tin chính** nếu thỏa ít nhất một trong ba điều kiện:

- Được nêu trong tiêu đề.
- Được nêu trong đoạn mở đầu của bài.
- Có từ 2 câu trở lên nói về sự kiện, kèm chi tiết cụ thể (số liệu, diễn biến, cơ quan xử lý). Một đề mục nhỏ trong bài cộng với một câu chi tiết cũng tính là 2 câu.

Nếu không thỏa điều kiện nào thì là **nhắc qua**, không tính là rủi ro. Ví dụ: một câu duy nhất nhắc lại sự việc cũ làm bối cảnh, một dòng "tin liên quan" chèn trong bài, hoặc một câu nêu số liệu giảm trong bài nói về chuyện khác.

# Không làm

- Không dùng hiểu biết bên ngoài bài báo về công ty, trừ các danh sách khớp nhầm, công ty con và đơn vị trực thuộc ở trên.
- Không suy diễn chi tiết bài không nêu.
- Không kết luận cho công ty không có trong danh sách được giao.
- Không viết gì ngoài đối tượng JSON.

# Khi không chắc chắn

Nếu không đủ thông tin để kết luận, ghi `rui_ro: false`, `muc_do: "khong_ro"`, và nêu lý do trong `ly_do`. Những ca này sẽ được người đọc lại. Dùng `khong_ro` cho các trường hợp sau:

- Bài bị cắt ngắn, sự kiện mô tả mơ hồ.
- Không rõ trách nhiệm thuộc về công ty hay bên khác (ví dụ người dân phản đối ô nhiễm nhưng chưa có kết luận, thanh tra kết luận sai phạm của cán bộ quản lý ngành còn công ty chỉ là nơi họ góp vốn).
- Tranh chấp giữa các cổ đông về cổ phần của công ty, công ty không phải một bên.
- Nguy cơ chưa xảy ra: nguy cơ vỡ phương án tài chính, nguy cơ phát sinh nợ xấu, dự án nguy cơ chậm tiến độ.
- Nợ lớn, "nghi vấn khả năng thanh toán", "món nợ" nhưng bài không nói nợ xấu hay chậm trả nợ.
- Công ty là chủ nợ bị khách hàng chậm trả.
- Lỗ do trích lập dự phòng hoặc đánh giá lại khoản đầu tư cổ phiếu, trong khi lợi nhuận chung của công ty vẫn tăng. Nếu chỉ nêu trong một câu thì ghi `nhac_qua`.
- Chưa đạt kế hoạch lợi nhuận nhưng bài không nói rõ lợi nhuận giảm; hoặc lợi nhuận giảm chỉ nêu một câu ở thân bài của chính bài kết quả kinh doanh mà tiêu đề, đoạn mở đầu không nói giảm.
- Lãnh đạo cấp cao bỏ trốn, mất liên lạc, nghỉ vô tổ chức nhưng chưa có quyết định miễn nhiệm hoặc sa thải.
- Cổ phiếu của công ty bị cá nhân bên ngoài thao túng; cổ phiếu bị đưa vào danh sách không được giao dịch ký quỹ; công ty không còn đủ điều kiện công ty đại chúng.
- Sự việc bất lợi không khớp rõ mục nào trong "Tính là rủi ro" (ví dụ đối thủ cạnh tranh không lành mạnh, dịch bệnh lây lan tại chi nhánh, cây trồng kém chất lượng phải bán thanh lý).

# Ví dụ

- Bài "Giám đốc Petrolimex Long An bị bắt". PLX: có rủi ro, tin chính. Petrolimex Long An là đơn vị trực thuộc không có mã riêng.
- Bài về Viglacera Đông Triều (DTC) báo lỗ, âm vốn. VGC: không có rủi ro. DTC có mã riêng.
- Bài "Chủ hãng bia Sài Gòn có doanh số thấp nhất 10 năm", trong khi lãi sau thuế tăng 2%. SAB: không có rủi ro. Chỉ doanh thu giảm.
- Bài về việc Sabeco tạm ứng cổ tức, có một câu "lãi 9 tháng giảm 1%". SAB: không có rủi ro. Chỉ một câu, không ở tiêu đề hay đoạn mở đầu, nên là nhắc qua.
- Bài kết quả kinh doanh của Petrolimex, có hai câu nêu lãi sau thuế quý IV giảm 30% và lãi công ty mẹ giảm 36%. PLX: có rủi ro, tin chính (có từ 2 câu kèm số liệu).
- Bài liệt kê lãnh đạo nhiều công ty bị bán giải chấp, có một đoạn về Chủ tịch và Tổng giám đốc Hải Phát. HDC: có rủi ro, tin chính.
- Bài về Vincom Retail thay Chủ tịch HĐQT, có nhắc Vingroup là công ty mẹ. VRE: có rủi ro, tin chính. VIC: không có rủi ro, VRE có mã riêng.
- Bài về vụ án tại GPBank, trong đó EVNFinance là bên mua trái phiếu và bị thiệt hại. EVF: có rủi ro. Là nạn nhân.

# Đầu vào

Mỗi lần bạn nhận:
- Tiêu đề và nội dung bài báo.
- Danh sách công ty cần xét, mỗi công ty gồm mã, tên đầy đủ và các tên gọi khác.

# Đầu ra

Chỉ trả lời bằng một đối tượng JSON. Mỗi công ty trong danh sách có đúng một dòng:

```json
{"ket_qua": [
  {"ticker": "mã công ty",
   "rui_ro": true hoặc false,
   "muc_do": "tin_chinh", "nhac_qua", "khong" hoặc "khong_ro",
   "loai": "một giá trị trong danh sách loai chuẩn, hoặc rỗng",
   "chu_the": "công ty thực sự gặp sự kiện bất lợi, hoặc rỗng",
   "bang_chung": "trích nguyên văn một câu ngắn trong bài, hoặc rỗng",
   "ly_do": "một câu giải thích kết luận"}
]}
```

Giá trị chuẩn cho `loai` (để rỗng khi `muc_do` là `khong`):

thay đổi lãnh đạo, lợi nhuận giảm, thua lỗ, kế hoạch lợi nhuận giảm, không chia được cổ tức, nợ xấu, chậm trả nợ, khởi tố, điều tra, thanh tra, lãnh đạo bị bắt, bị xử phạt, truy thu thuế, vi phạm, cổ phiếu bị cảnh báo, kiểm toán điều chỉnh giảm, kiện tụng, tranh chấp, tin đồn, khiếu nại của khách hàng, bị bán giải chấp, bị mạo danh, bị lừa đảo, bị tấn công mạng, nạn nhân, dự án đình trệ, dự án chậm tiến độ, sự cố, tai nạn, thiệt hại do thiên tai.

Với `khong_ro`, `loai` ghi loại sự kiện gần nhất, kể cả loại chưa có trong danh sách (ví dụ khó khăn tài chính, thao túng cổ phiếu, khách hàng chậm trả nợ).

Với `ly_do` của kết luận `khong`:
- Khớp nhầm: nêu tên bị nhầm là gì (ví dụ "KDC là khu dân cư, khớp nhầm").
- Có sự kiện nhưng không thuộc công ty này hoặc không thuộc mục rủi ro: nêu ngắn sự kiện và lý do.
- Không có sự kiện bất lợi nào: ghi "không có sự kiện bất lợi của chính công ty này trong bài".

# Tự kiểm tra trước khi trả lời

- Mỗi công ty trong danh sách có đúng một dòng, không thiếu, không thừa.
- `rui_ro` chỉ là `true` khi `muc_do` là `tin_chinh`, và ngược lại.
- `bang_chung` là câu trích nguyên văn từ bài, không diễn đạt lại.
- Mỗi kết luận `tin_chinh` thỏa ít nhất một trong ba điều kiện ở mục "Tin chính hay chỉ nhắc qua".
- Không công ty con có mã riêng nào bị tính rủi ro thay cho công ty mẹ, hoặc ngược lại.
- `loai` dùng giá trị trong danh sách chuẩn khi `muc_do` là `tin_chinh` hoặc `nhac_qua`.
- Không có chữ nào ngoài đối tượng JSON.
