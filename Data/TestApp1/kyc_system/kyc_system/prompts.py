"""Các prompt. Prompt đọc bài giữ đúng bản v2 đã đánh giá trên benchmark."""

RULES_V2 = """Định nghĩa "sự kiện bất lợi" (rủi ro) của một công ty, dùng cho sàng lọc KYC:

TÍNH là rủi ro nếu chính công ty là chủ thể của:
- vi phạm, bị xử phạt, bị điều tra, thanh tra, khởi tố, lãnh đạo bị bắt vì việc của công ty
- là nạn nhân: bị cướp, bị mạo danh, bị lừa đảo, bị tấn công mạng
- tranh chấp, bị kiện, kiện tụng tại tòa (kể cả khi thắng kiện)
- tin đồn ảnh hưởng tới công ty, khiếu nại của khách hàng
- khó khăn tài chính: thua lỗ, lợi nhuận giảm, kế hoạch lợi nhuận giảm, nợ xấu, giải chấp, chậm trả nợ, khất cổ tức, cổ phiếu giảm sàn nhiều phiên kèm khó khăn
- kiểm toán điều chỉnh giảm, dự án đình trệ, thiệt hại do thiên tai, sự cố, tai nạn
- thay đổi lãnh đạo cấp cao: chủ tịch, thành viên HĐQT, tổng giám đốc, phó tổng giám đốc, trưởng ban kiểm soát, kế toán trưởng (từ nhiệm, miễn nhiệm, bổ nhiệm mới, qua đời)

KHÔNG tính là rủi ro:
- danh sách ủng hộ từ thiện, quảng cáo, giải thưởng, hợp tác, ra mắt sản phẩm
- biến động chung của thị trường chứng khoán, chỉ doanh thu giảm (lợi nhuận không giảm)
- thay đổi sở hữu, thoái vốn, cổ đông mua bán cổ phiếu
- ngân hàng bán tài sản thế chấp của khách hàng vay, công ty là bên đi khiếu nại trong đấu thầu
- công ty chỉ được nhắc qua, còn sự kiện bất lợi thuộc về công ty khác

Công ty con có mã chứng khoán riêng (ví dụ Vincom Retail là VRE, Vinhomes là VHM, chứng khoán BSI, CTS, VIX): sự kiện thuộc về công ty con, không tính cho công ty mẹ.

Đơn vị không có mã chứng khoán riêng: chi nhánh, công ty xăng dầu tỉnh, đơn vị thành viên, công ty con chưa niêm yết (kể cả khi tên khác công ty mẹ). Sự kiện bất lợi của các đơn vị này, hoặc của lãnh đạo, cán bộ các đơn vị này trong công việc, TÍNH cho công ty mẹ. Vẫn tính kể cả khi công ty mẹ tuyên bố đó là hành vi cá nhân.
Ví dụ: Giám đốc một công ty xăng dầu tỉnh thuộc Petrolimex bị bắt -> tính cho PLX.

Sự kiện bất lợi phải là tin mà bài đưa (kết quả kinh doanh của kỳ đang báo cáo, sự việc đang xảy ra). KHÔNG tính khi bài chủ yếu đưa tin tích cực và chỉ nhắc lại một khó khăn cũ làm bối cảnh.
Ví dụ: bài "lợi nhuận quý này tăng mạnh, cải thiện so với quý trước bị lỗ" -> không tính."""


def read_prompt(ticker, company_line, title, text):
    return f"""{RULES_V2}

Công ty cần sàng lọc: {company_line}

Bài báo:
Tiêu đề: {title}
Nội dung: {text}

Trả lời CHỈ bằng một đối tượng JSON, không viết gì thêm:
{{"lien_quan": true hoặc false (bài có đưa tin sự kiện bất lợi mà chính công ty {ticker} là chủ thể),
  "chu_the": "mã hoặc tên công ty thực sự gặp sự kiện bất lợi trong bài, hoặc rỗng nếu không có",
  "loai_su_kien": "ví dụ: khởi tố, kiện tụng, thua lỗ, thay đổi lãnh đạo, bị cướp, ... hoặc rỗng",
  "vai_tro": "vai trò của {ticker}: chủ thể, đơn vị trực thuộc là chủ thể, bên bị hại, chỉ được nhắc qua, ...",
  "mo_ta": "một câu mô tả sự kiện bất lợi, hoặc rỗng",
  "bang_chung": "trích nguyên văn một câu ngắn trong bài làm bằng chứng, hoặc rỗng"}}"""


GROUP_PROMPT = """Below is a list of news articles about adverse events of the company {company}.
Group together articles that report the SAME event or the same chain of related developments
(for example: an executive being suspended, then dismissed, then prosecuted is one event).
Articles about different events must be in different groups.

Articles (id | date | event type | description):
{lines}

Reply ONLY with a JSON object: {{"groups": [[id, id, ...], [id, ...], ...]}}
Every id must appear in exactly one group."""


EVENT_PROMPT = """You are a KYC analyst writing one entry of a due diligence report on {company}.
Using ONLY the source articles below, write an English summary of this adverse event.

Rules:
- One paragraph of 80-150 words covering 5W1H: who, what, when, where, why, how. If a point is not in the sources, write "not stated".
- Every sentence must end with a citation such as [1] or [1][2] pointing to the source numbers below. Do not use facts that are not in the sources.
- Vietnamese person names: family name in capitals, no diacritics, e.g. "NGUYEN Ba Duong". Use the full name at first mention and in the headline. After that, write "Mr." or "Ms." plus the family name, e.g. "Mr. NGUYEN". Never refer to a person by the given name alone.
- Focus on the adverse event itself. Leave out business or financial details that do not help explain the event.
- Companies: international name with ticker if listed, e.g. "Petrolimex (PLX)", "Vincom Retail (VRE)".
- Translate job titles into English (Chairman, CEO, Deputy CEO, Board member...). Amounts as "VND 662 billion".
- No Vietnamese words in the output.

Sources:
{sources}

Reply ONLY with a JSON object:
{{"headline": "short English headline in sentence case (only the first word and names capitalised) that states the adverse fact itself, e.g. the loss, the charge, the dismissal",
  "date": "date of the event, YYYY-MM-DD or YYYY-MM",
  "category": "one of: Regulatory/Legal, Litigation, Fraud/Crime, Financial distress, Leadership change, Incident, Reputation",
  "summary": "the paragraph"}}"""


OVERVIEW_PROMPT = """You are a KYC analyst. Below are the adverse events found in Vietnamese news about {company}.

{items}

Write ONLY a JSON object:
{{"company_name_en": "international name of the company",
  "overview": "3-5 English sentences: the main risk themes, the most serious and the most recent events, and whether problems are ongoing. Judge seriousness by the harm to the company; an outcome favourable to the company is never the most serious event. No citations, no Vietnamese words."}}"""
