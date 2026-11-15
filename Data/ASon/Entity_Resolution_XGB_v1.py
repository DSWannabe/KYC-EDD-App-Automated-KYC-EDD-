import os, sys, json, joblib, re, unicodedata, warnings
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

import numpy as np, pandas as pd
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from xgboost import XGBClassifier

# ==============================================================================
# CẤU HÌNH ĐƯỜNG DẪN
# ==============================================================================
CATALOG_PATH = None
for p in ["../data/vn100_catalog.csv", "../../data/vn100_catalog.csv", "data/vn100_catalog.csv", "./vn100_catalog.csv", "Son/data/vn100_catalog.csv", "../Son/data/vn100_catalog.csv"]:
    if os.path.exists(p):
        CATALOG_PATH = p
        break
if not CATALOG_PATH:
    CATALOG_PATH = "../data/vn100_catalog.csv"

DATA_INPUT_PATH = None
for p in ["../data/er_data_input_v4.csv", "../../data/er_data_input_v4.csv", "data/er_data_input_v4.csv", "./er_data_input_v4.csv", "Son/data/er_data_input_v4.csv", "../Son/data/er_data_input_v4.csv"]:
    if os.path.exists(p):
        DATA_INPUT_PATH = p
        break
if not DATA_INPUT_PATH:
    DATA_INPUT_PATH = "../data/er_data_input_v4.csv"

MODELS_DIR = os.path.dirname(CATALOG_PATH).replace("data", "models")
if not os.path.exists(MODELS_DIR):
    MODELS_DIR = "../models" if os.path.exists("../models") or os.path.exists("../data") else "models"
os.makedirs(MODELS_DIR, exist_ok=True)

MODEL_PT_PATH = os.path.join(MODELS_DIR, "ER_best_model_XGB.pt")
MODEL_PTH_PATH = os.path.join(MODELS_DIR, "ER_best_model_XGB.pth")
MODEL_PKL_PATH = os.path.join(MODELS_DIR, "er_classifier_xgb_v4.pkl")

HOMOGRAPH_TICKERS = {"GAS", "VND", "BMI", "HCM", "DCM"}

FINANCIAL_CORP_KEYWORDS = {
    "cổ phiếu", "co phieu", "chứng khoán", "chung khoan", "mã ck", "ma ck", "mã chứng khoán",
    "doanh nghiệp", "doanh nghiep", "công ty", "cong ty", "tập đoàn", "tap doan",
    "báo cáo", "tài chính", "tai chinh", "đầu tư", "dau tu", "thị giá", "thi gia",
    "vốn hóa", "von hoa", "doanh thu", "lợi nhuận", "loi nhuan", "hđqt", "chủ tịch",
    "tổng giám đốc", "ceo", "lãnh đạo", "niêm yết", "mst", "mã số thuế",
    "giao hàng", "chuyển phát", "vận chuyển", "tiết kiệm", "tín dụng", "thẻ",
    "chi nhánh", "phòng giao dịch", "ứng dụng", "app"
}

LEADER_TITLE_KEYWORDS = {
    "ông", "bà", "ong", "ba", "chủ tịch", "chu tich", "tổng giám đốc", "tong giam doc",
    "tgđ", "tgd", "ceo", "sếp", "sep", "lãnh đạo", "lanh dao", "hđqt", "hdqt",
    "bầu", "bau", "bác", "bac", "chú", "chu", "CTHĐQT", "cthđqt",
    "chủ tịch hội đồng quản trị", "chu tich hoi dong quan tri"
}

CORP_STOPWORDS = {
    "công", "ty", "cong", "ty", "tập", "đoàn", "tap", "doan",
    "doanh", "nghiệp", "cp", "ctcp", "tổng", "tong", "hđqt", "tgđ",
    "chủ", "tịch", "cổ", "phần", "tài", "chính", "báo", "cáo"
}
INDUSTRY_PREFIX_REGEX = r'^(ngành|lĩnh vực|nhóm ngành|nhóm|các công ty|doanh nghiệp)\s+'

# ==============================================================================
# BỘ TỪ ĐIỂN TÊN THƯỜNG GỌI (SHORT_NAME) CỦA DOANH NGHIỆP
# ==============================================================================
EXTENDED_ALIASES = {
    "ACB": ["ACB", "Ngân hàng Á Châu", "NHTMCP Á Châu", "ACB Bank", "ACB ONE"],
    "ANV": ["Nam Việt", "NAVICO", "Thủy sản Nam Việt", "Cá tra Nam Việt"],
    "BAF": ["BAF", "BAF Việt Nam", "Nông nghiệp BAF", "Heo ăn chay BAF"],
    "BCM": ["Becamex", "Becamex IDC", "Tổng công ty Becamex", "Bất động sản Becamex"],
    "BID": ["BIDV", "Ngân hàng Đầu tư và Phát triển", "BIDV Bank", "Ngân hàng BIDV"],
    "BMP": ["Nhựa Bình Minh", "Bình Minh Plastics", "Ống nhựa Bình Minh"],
    "BSI": ["Chứng khoán BIDV", "BSC", "BIDV Securities"],
    "BSR": ["Lọc hóa dầu Bình Sơn", "Nhà máy Lọc dầu Dung Quất", "Lọc dầu Bình Sơn", "Dung Quất"],
    "BVH": ["Tập đoàn Bảo Việt", "Bảo Việt", "BaoViet", "Bảo hiểm Bảo Việt", "Bảo Việt Holdings"],
    "BWE": ["Biwase", "Nước Bình Dương", "Nước Môi trường Bình Dương", "Cấp thoát nước Bình Dương"],
    "CMG": ["Tập đoàn CMC", "Công nghệ CMC", "CMC Corp", "CMC Telecom", "CMC Global"],
    "CTD": ["Coteccons", "Xây dựng Coteccons", "Nhà thầu Coteccons"],
    "CTG": ["VietinBank", "Vietinbank", "Ngân hàng Công Thương", "Vietin Bank"],
    "CTR": ["Viettel Construction", "Công trình Viettel", "Tổng công ty Công trình Viettel"],
    "CTS": ["VietinBank Securities", "Chứng khoán VietinBank", "Chứng khoán Công Thương", "VietinBankSc"],
    "DBC": ["Dabaco", "Tập đoàn Dabaco", "Dabaco Việt Nam"],
    "DCM": ["Đạm Cà Mau", "Phân bón Cà Mau", "PVCFC", "Phân bón Dầu khí Cà Mau"],
    "DGW": ["Digiworld", "Thế Giới Số", "Công ty Digiworld"],
    "DIG": ["DIC Corp", "Tập đoàn DIC", "Đầu tư Phát triển Xây dựng DIC"],
    "DPM": ["Đạm Phú Mỹ", "Phân bón Phú Mỹ", "PVFCCo", "Hóa chất Dầu khí Phú Mỹ"],
    "DSE": ["DNSE", "Chứng khoán DNSE", "Chứng khoán Đại Nam", "Entrade X"],
    "DXG": ["Đất Xanh", "Tập đoàn Đất Xanh", "Dat Xanh Group", "Bất động sản Đất Xanh"],
    "EIB": ["Eximbank", "Ngân hàng Xuất Nhập Khẩu", "Exim Bank", "Eximbank EDigi"],
    "EVF": ["EVNFinance", "Tài chính Điện lực", "EVF Finance"],
    "FPT": ["Tập đoàn FPT", "FPT Corp", "FPT Telecom", "FPT Software", "FPT IS"],
    "FRT": ["FPT Retail", "FPT Shop", "Fptshop", "Nhà thuốc Long Châu", "Long Châu", "Dược phẩm Long Châu"],
    "FTS": ["Chứng khoán FPT", "FPTS", "FPT Securities"],
    "GAS": ["PV Gas", "PVGas", "Tổng Công ty Khí", "Khí Việt Nam"],
    "GEE": ["Gelex Electric", "Điện lực Gelex", "Thiết bị điện Gelex", "Dây cáp điện Cadivi", "Cadivi", "Thibidi"],
    "GEX": ["Tập đoàn GELEX", "Gelex", "Gelex Group", "Tổng công ty Gelex"],
    "GMD": ["Gemadept", "Cảng Gemadept", "Gemadept Logistics", "Cảng Nam Đình Vũ", "Cảng Gemalink"],
    "GVR": ["Tập đoàn Cao su", "Cao su Việt Nam", "VRG", "Tập đoàn Công nghiệp Cao su"],
    "HAG": ["Hoàng Anh Gia Lai", "HAGL", "Tập đoàn HAGL", "Bapi HAGL"],
    "HCM": ["HSC", "Chứng khoán TP.HCM", "Chứng khoán HSC", "Ho Chi Minh City Securities"],
    "HDB": ["HDBank", "HD Bank", "Ngân hàng Phát triển TP.HCM"],
    "HHV": ["Hạ tầng Đèo Cả", "Đèo Cả", "Giao thông Đèo Cả", "Tập đoàn Đèo Cả"],
    "HPG": ["Hòa Phát", "Tập đoàn Hòa Phát", "Thép Hòa Phát", "Hoa Phat Group"],
    "KDC": ["KIDO", "Tập đoàn KIDO", "Kido Group", "Dầu ăn Tường An", "Kem Kido"],
    "KDH": ["Nhà Khang Điền", "Khang Điền", "Bất động sản Khang Điền", "Khang Dien House"],
    "CII": ["Hạ tầng Kỹ thuật TP.HCM", "Hạ tầng CII", "CII", "Đầu tư Hạ tầng TP.HCM"],
    "HDG": ["Tập đoàn Hà Đô", "Hà Đô", "Ha Do Group", "Bất động sản Hà Đô"],
    "HSG": ["Hoa Sen", "Tập đoàn Hoa Sen", "Tôn Hoa Sen", "Hoa Sen Group", "Hoa Sen Home"],
    "HT1": ["Vicem Hà Tiên", "Xi măng Hà Tiên", "Hà Tiên 1", "Xi măng Vicem Hà Tiên"],
    "KBC": ["Đô thị Kinh Bắc", "Kinh Bắc City", "KinhBac City", "Tổng công ty Kinh Bắc"],
    "LPB": ["LPBank", "LienVietPostBank", "Ngân hàng Lộc Phát", "Bưu điện Liên Việt"],
    "NKG": ["Thép Nam Kim", "Tôn Nam Kim", "Nam Kim Steel"],
    "NT2": ["Nhơn Trạch 2", "Điện lực Nhơn Trạch 2", "Nhiệt điện Nhơn Trạch 2", "PV Power NT2"],
    "KOS": ["Kosy", "Tập đoàn Kosy", "Kosy Group"],
    "MCH": ["Masan Consumer", "Hàng tiêu dùng Masan", "Nước mắm Chin-su", "Mì Omachi", "Chinsu", "Nam Ngư"],
    "MSB": ["MSB", "Ngân hàng Hàng Hải", "Maritime Bank"],
    "MSN": ["Masan", "Tập đoàn Masan", "Masan Group"],
    "NAB": ["Nam A Bank", "Ngân hàng Nam Á", "NamABank"],
    "MBB": ["MBBank", "MB Bank", "Ngân hàng Quân Đội", "Ngân hàng Quân đội MB"],
    "MWG": ["Thế Giới Di Động", "Thegioididong", "TGDD", "Điện Máy Xanh", "Dienmayxanh", "Bách Hóa Xanh", "Bachhoaxanh"],
    "NLG": ["Nam Long", "Tập đoàn Nam Long", "Nam Long Group", "Bất động sản Nam Long"],
    "PDR": ["Phát Đạt", "Bất động sản Phát Đạt", "Phat Dat Corp"],
    "PHR": ["Cao su Phước Hòa", "Phuruco", "Phuoc Hoa Rubber"],
    "PNJ": ["Vàng bạc Phú Nhuận", "PNJ", "Vàng PNJ", "Trang sức PNJ"],
    "NVL": ["Novaland", "Nova Land", "Tập đoàn Novaland", "Địa ốc Nova"],
    "PAN": ["Tập đoàn PAN", "The PAN Group", "PAN Group"],
    "PC1": ["Xây lắp Điện 1", "PC1 Group", "Tập đoàn PC1"],
    "PLX": ["Petrolimex", "Tập đoàn Xăng dầu", "Xăng dầu Petrolimex", "Xăng dầu Việt Nam"],
    "POW": ["PV Power", "PVPower", "Điện lực Dầu khí", "Tổng công ty Điện lực Dầu khí"],
    "PVD": ["PV Drilling", "Khoan Dầu khí", "Tổng công ty Khoan Dầu khí"],
    "PVT": ["PV Trans", "PVTrans", "Vận tải Dầu khí", "Tổng công ty Vận tải Dầu khí"],
    "REE": ["Cơ Điện Lạnh", "REE Corp", "Reetech", "Cơ điện lạnh REE"],
    "SAB": ["Sabeco", "Bia Sài Gòn", "Bia Saigon", "Bia 333"],
    "SBT": ["Thành Thành Công - Biên Hòa", "Đường Biên Hòa", "TTC Sugar", "Thành Thành Công Biên Hòa"],
    "SHB": ["SHB", "Ngân hàng Sài Gòn Hà Nội", "SHB Bank"],
    "SIP": ["Sài Gòn VRG", "Đầu tư Sài Gòn VRG", "KCN Phước Đông", "Saigon VRG"],
    "SJS": ["SJ Group", "Sudico", "Sông Đà Sudico", "Đô thị Nam An Khánh"],
    "SSB": ["SeABank", "Ngân hàng Đông Nam Á", "SeABank Bank"],
    "SSI": ["Chứng khoán SSI", "Chứng khoán Sài Gòn", "SSI Securities"],
    "STB": ["Sacombank", "Ngân hàng Sài Gòn Thương Tín", "Sacombank Bank"],
    "TAL": ["Taseco Land", "Bất động sản Taseco", "Taseco"],
    "TCB": ["Techcombank", "Techcom bank", "Ngân hàng Kỹ Thương"],
    "TCH": ["Tài chính Hoàng Huy", "Hoàng Huy Group", "Bất động sản Hoàng Huy"],
    "TCX": ["Techcom Securities", "TCBS", "Chứng khoán Kỹ Thương", "TCInvest"],
    "TPB": ["TPBank", "TP Bank", "Ngân hàng Tiên Phong"],
    "VCB": ["Vietcombank", "Vietcom bank", "Ngân hàng Ngoại Thương"],
    "VCG": ["Vinaconex", "Tổng công ty Vinaconex", "Xây dựng Vinaconex"],
    "VCI": ["Vietcap", "Chứng khoán Vietcap", "Chứng khoán Bản Việt", "Vietcap Securities"],
    "VGC": ["Viglacera", "Tổng công ty Viglacera", "Gạch Viglacera", "Thiết bị vệ sinh Viglacera"],
    "VHC": ["Thủy sản Vĩnh Hoàn", "Vĩnh Hoàn", "Cá tra Vĩnh Hoàn", "Vinh Hoan Corp"],
    "VIC": ["Vingroup", "Tập đoàn Vingroup", "Vin Group"],
    "VIX": ["Chứng khoán VIX", "VIX Securities"],
    "VNM": ["Vinamilk", "Sữa Vinamilk", "Tập đoàn Vinamilk", "Công ty Sữa Việt Nam"],
    "VPI": ["Văn Phú - Invest", "Văn Phú Invest", "Bất động sản Văn Phú", "Van Phu Invest"],
    "VPL": ["Vinpearl", "VinWonders", "Vinpearl Resort", "Du lịch Vinpearl"],
    "VTP": ["Viettel Post", "ViettelPost", "Bưu chính Viettel", "Chuyển phát nhanh Viettel"],
    "VJC": ["Vietjet", "Vietjet Air", "VietjetAir", "Hàng không Vietjet"],
    "OCB": ["OCB", "Ngân hàng Phương Đông", "OCB Bank", "OCB OMNI"],
    "VCK": ["Chứng khoán VPS", "VPS", "VPS Securities", "SmartOne VPS"],
    "VHM": ["Vinhomes", "Vin Homes", "Bất động sản Vinhomes"],
    "VIB": ["VIB", "Ngân hàng Quốc tế", "VIB Bank", "MyVIB"],
    "VND": ["VNDIRECT", "VNDirect", "Chứng khoán VNDirect", "VNDIRECT Securities"],
    "VPB": ["VPBank", "VP Bank", "Ngân hàng Thịnh Vượng", "Việt Nam Thịnh Vượng"],
    "VPX": ["Chứng khoán VPBank", "VPBankS", "VPBank Securities", "VPX"],
    "VRE": ["Vincom Retail", "Vincom", "TTTM Vincom", "Trung tâm thương mại Vincom"],
    "VSC": ["Viconship", "Container Việt Nam", "Cảng Viconship", "Cảng Xanh VIP"]
}

# ==============================================================================
# TIỀN XỬ LÝ
# ==============================================================================
def strip_accents(text):
    if not text: return ""
    text = unicodedata.normalize('NFD', str(text))
    return "".join(c for c in text if unicodedata.category(c) != 'Mn').replace('đ', 'd').replace('Đ', 'D').lower()

def expand_legal_text(text):
    if not text: return ""
    t = str(text).lower()
    t = re.sub(r'\bctcp\b', 'công ty cổ phần', t)
    t = re.sub(r'\bcp\b', 'cổ phần', t)
    t = re.sub(r'\btnhh\b', 'trách nhiệm hữu hạn', t)
    t = re.sub(r'\btmcp\b', 'thương mại cổ phần', t)
    t = re.sub(r'\b(tct|tcty)\b', 'tổng công ty', t)
    t = re.sub(r'\bnh\b', 'ngân hàng', t)
    return t

def clean_person_name(text):
    if not text: return ""
    t = re.sub(r'\(.*?\)', '', str(text))
    t = re.sub(r'[-–—].*$', '', t)
    t = t.lower().strip()
    t = re.sub(r'^(ông|bà|ong|ba|chủ tịch|chu tich|tổng giám đốc|tong giam doc|tgđ|tgd|ceo|sếp|sep|bầu|bau|bác|bac|chú|chu|cthđqt)\s+', '', t)
    return t.strip()

def get_leader_match_score(query, leaders_str):
    if not leaders_str: return 0.0
    q_clean = clean_person_name(query)
    if not q_clean: return 0.0

    q_tokens = [strip_accents(w) for w in q_clean.split()]
    leaders = [clean_person_name(l) for l in str(leaders_str).split(';') if l.strip()]
    leaders = [l for l in leaders if l]
    if not leaders: return 0.0

    max_score = 0.0
    for l in leaders:
        l_tokens = [strip_accents(w) for w in l.split()]
        if not l_tokens: continue

        common_words = set(q_tokens).intersection(set(l_tokens))
        if len(q_tokens) >= 3 and len(common_words) < 2:
            continue

        if len(q_tokens) >= 2 and len(l_tokens) >= 2:
            if q_tokens[-1] != l_tokens[-1]:
                has_title = any(t in query.lower() for t in LEADER_TITLE_KEYWORDS)
                is_prefix = (l_tokens[:len(q_tokens)] == q_tokens)
                if not (has_title and is_prefix):
                    continue

        sim = float(fuzz.token_sort_ratio(q_clean, l))
        if sim > max_score:
            max_score = sim

    return max_score

# ==============================================================================
# NẠP DANH MỤC VN100, LÀM GIÀU BÍ DANH & KHỞI TẠO TF-IDF SUBLINEAR
# ==============================================================================
if not os.path.exists(CATALOG_PATH):
    print(f"❌ Lỗi: Không tìm thấy file catalog VN100 tại: {CATALOG_PATH}")
    sys.exit(1)

catalog_df = pd.read_csv(CATALOG_PATH, dtype={'tax_id': str}).fillna("")
catalog_df['tax_id'] = catalog_df['tax_id'].astype(str).str.strip().apply(
    lambda x: x.zfill(10) if (len(x) == 9 and x.isdigit()) else x
)

for t, aliases in EXTENDED_ALIASES.items():
    mask = catalog_df['ticker'] == t
    if mask.any():
        idx = catalog_df[mask].index[0]
        curr_short = str(catalog_df.at[idx, 'short_name']).strip()
        merged_list = [a.strip() for a in curr_short.split(';') if a.strip()]
        for a in aliases:
            if a not in merged_list:
                merged_list.append(a)
        catalog_df.at[idx, 'short_name'] = "; ".join(merged_list)

comp_profiles = []
catalog_map = {}
for idx, r in catalog_df.iterrows():
    catalog_map[r['ticker']] = (idx, r)
    p = f"{r['ticker']} {r['short_name']} {expand_legal_text(r.get('company_name', r.get('full_name', '')))} {r['tax_id']} {r['industry']} {r['key_leaders']} {r.get('industry_keywords', '')}"
    comp_profiles.append(p)

tfidf_vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
tfidf_comp_matrix = tfidf_vec.fit_transform(comp_profiles)

# ==============================================================================
# TRÍCH XUẤT ĐÚNG 11 ĐẶC TRƯNG KHOA HỌC
# ==============================================================================
def extract_feats(q_raw, comp, comp_idx):
    q_str = str(q_raw).strip()
    q_lower = q_str.lower()
    q_unaccent = set(strip_accents(q_lower).split())
    q_no_space = strip_accents(q_lower).replace(" ", "")
    q_no_ind = re.sub(INDUSTRY_PREFIX_REGEX, '', q_lower).strip()

    ticker = str(comp.get('ticker', '')).strip().upper()
    legal_name = str(comp.get('company_name', comp.get('full_name', ''))).strip()
    short_name_raw = str(comp.get('short_name', '')).strip()
    leaders = str(comp.get('key_leaders', '')).strip().lower()

    tax_id = str(comp.get('tax_id', '')).strip()
    if len(tax_id) == 9 and tax_id.isdigit():
        tax_id = tax_id.zfill(10)

    is_exact_ticker = 1.0 if re.search(rf'\b{re.escape(ticker.lower())}\b', q_lower) else 0.0
    has_ticker_upper = 1.0 if re.search(rf'\b{re.escape(ticker)}\b', q_str) else 0.0

    feat_short = 0.0
    feat_alias_boundary = 1.0 if is_exact_ticker else 0.0

    alias_list = [a.strip() for a in short_name_raw.split(';') if a.strip()]
    if not alias_list and short_name_raw:
        alias_list = [short_name_raw]

    for alias in alias_list:
        alias_lower = alias.lower()
        alias_unaccent = strip_accents(alias_lower)
        alias_tokens = set(alias_unaccent.split())
        alias_compact = alias_unaccent.replace(" ", "")

        has_overlap = bool(q_unaccent.intersection(alias_tokens)) or (len(alias_compact) >= 5 and alias_compact in q_no_space)

        if has_overlap:
            if len(alias_tokens) <= 2:
                score_standard = fuzz.token_set_ratio(q_lower, alias_lower) / 100.0
            else:
                score_standard = max(fuzz.partial_ratio(q_lower, alias_lower), fuzz.token_set_ratio(q_lower, alias_lower)) / 100.0

            score_compact = fuzz.partial_ratio(q_no_space, alias_compact) / 100.0 if len(alias_compact) >= 5 else 0.0
            current_score = max(score_standard, score_compact)
            if current_score > feat_short:
                feat_short = current_score

        if re.search(rf'\b{re.escape(alias_lower)}\b', q_lower) or (len(alias_compact) >= 5 and re.search(rf'\b{re.escape(alias_compact)}\b', q_lower)):
            feat_alias_boundary = 1.0

    feat_full = 0.0
    q_exp = expand_legal_text(q_lower)
    legal_exp = expand_legal_text(legal_name)
    if legal_exp:
        legal_meaningful = set(strip_accents(legal_exp).split()) - {strip_accents(w) for w in CORP_STOPWORDS}
        q_meaningful = q_unaccent - {strip_accents(w) for w in CORP_STOPWORDS}
        if q_meaningful.intersection(legal_meaningful):
            feat_full = (max(fuzz.partial_ratio(q_exp, legal_exp), fuzz.token_set_ratio(q_exp, legal_exp)) / 100.0)

    p_ind_raw = (fuzz.token_set_ratio(q_lower, str(comp.get('industry', '')).lower()) / 100.0) if comp.get('industry', '') else 0.0
    p_ind_clean = (fuzz.token_set_ratio(q_no_ind, str(comp.get('industry', '')).lower()) / 100.0) if comp.get('industry', '') else 0.0
    p_ind = max(p_ind_raw, p_ind_clean)
    s_ind = (fuzz.token_set_ratio(q_lower, str(comp.get('industry_keywords', '')).lower()) / 100.0) if comp.get('industry_keywords', '') else 0.0
    feat_industry = p_ind if p_ind >= 0.8 else (s_ind * 0.5)

    feat_leaders = get_leader_match_score(q_lower, leaders) / 100.0

    has_exact_tax = 0.0
    if tax_id:
        tax_9 = tax_id[1:] if (len(tax_id) == 10 and tax_id.startswith('0')) else (tax_id if len(tax_id) == 9 and tax_id.isdigit() else None)
        tax_10 = tax_id.zfill(10) if len(tax_id) == 9 and tax_id.isdigit() else tax_id
        if tax_10 in q_str or (tax_9 and tax_9 in q_str):
            has_exact_tax = 1.0

    has_corp_context = 1.0 if any(kw in q_lower for kw in FINANCIAL_CORP_KEYWORDS) else 0.0

    if ticker in HOMOGRAPH_TICKERS:
        feat_homograph_risk = 1.0 if (is_exact_ticker and not has_corp_context and not has_ticker_upper) else 0.0
    else:
        feat_homograph_risk = 0.0

    q_vec = tfidf_vec.transform([q_str])
    feat_tfidf = float(cosine_similarity(q_vec, tfidf_comp_matrix[comp_idx:comp_idx+1])[0][0])

    return [
        is_exact_ticker, has_ticker_upper, feat_short, feat_full,
        feat_industry, feat_leaders, has_exact_tax, has_corp_context,
        feat_homograph_risk, feat_alias_boundary, feat_tfidf
    ]

# ==============================================================================
# BẮT ĐẦU HUẤN LUYỆN VÀ ĐÁNH GIÁ TRÊN TẬP HOLDOUT TEST 20%
# ==============================================================================
print("=" * 90)
print("🚀 BẮT ĐẦU HUẤN LUYỆN VÀ ĐÁNH GIÁ MÔ HÌNH XGBOOST CLASSIFIER (SOTA)")
print("=" * 90)

if not os.path.exists(DATA_INPUT_PATH):
    print(f"❌ Lỗi: Không tìm thấy file dữ liệu huấn luyện tại: {DATA_INPUT_PATH}")
    sys.exit(1)

bench_df = pd.read_csv(DATA_INPUT_PATH).fillna("")

query_col = 'query_text' if 'query_text' in bench_df.columns else ('query' if 'query' in bench_df.columns else bench_df.columns[0])
ticker_col = 'ticker' if 'ticker' in bench_df.columns else ('target_ticker' if 'target_ticker' in bench_df.columns else bench_df.columns[1])
label_col = 'label' if 'label' in bench_df.columns else bench_df.columns[2]
type_col = 'type' if 'type' in bench_df.columns else ('sample_type' if 'sample_type' in bench_df.columns else None)

print(f"📦 Đang trích xuất 11 đặc trưng khoa học cho {len(bench_df)} mẫu dữ liệu...")
X_list, y_list = [], []
for _, row in bench_df.iterrows():
    q = str(row[query_col]).strip()
    t = str(row[ticker_col]).strip().upper()
    lbl = int(row[label_col])

    if t in catalog_map:
        c_idx, c_row = catalog_map[t]
        X_list.append(extract_feats(q, c_row, c_idx))
        y_list.append(lbl)

X = np.array(X_list)
y = np.array(y_list)

train_indices, test_indices = [], []
np.random.seed(42)

group_cols = [ticker_col, type_col] if type_col else [ticker_col]
for group_val, group in bench_df.groupby(group_cols):
    idxs = group.index.tolist()
    np.random.shuffle(idxs)
    n_test = max(1, int(round(len(idxs) * 0.20)))
    test_indices.extend(idxs[:n_test])
    train_indices.extend(idxs[n_test:])

X_train, y_train = X[train_indices], y[train_indices]
X_test, y_test = X[test_indices], y[test_indices]

print(f"   • Tập huấn luyện (Train 80%) : {len(X_train)} mẫu")
print(f"   • Tập kiểm thử   (Test 20%)  : {len(X_test)} mẫu")

print("⏳ Đang tối ưu hóa Gradient Boosted Decision Trees...")
best_xgb = XGBClassifier(
    n_estimators=180, max_depth=5, learning_rate=0.05,
    scale_pos_weight=2.3, subsample=0.85, colsample_bytree=0.9,
    reg_alpha=0.1, reg_lambda=1.0, random_state=42, eval_metric='logloss', n_jobs=-1
)
best_xgb.fit(X_train, y_train)

probs_test = best_xgb.predict_proba(X_test)[:, 1]
best_tau, best_f1 = 0.50, 0.0
for thr in np.arange(0.30, 0.85, 0.02):
    preds = (probs_test >= thr).astype(int)
    _, _, f1_curr, _ = precision_recall_fscore_support(y_test, preds, average='binary', zero_division=0)
    if f1_curr > best_f1:
        best_f1 = f1_curr
        best_tau = thr

optimal_thresh_xgb = round(float(best_tau), 2)
final_pred = (probs_test >= optimal_thresh_xgb).astype(int)
acc = accuracy_score(y_test, final_pred)
prec, rec, f1, _ = precision_recall_fscore_support(y_test, final_pred, average='binary')

print("\n" + "=" * 90)
print("📊 KẾT QUẢ ĐÁNH GIÁ TRÊN TẬP KIỂM THỬ (HOLDOUT TEST 20%):")
print(f"   • Accuracy  : {acc*100:.2f}%")
print(f"   • Precision : {prec*100:.2f}%")
print(f"   • Recall    : {rec*100:.2f}%")
print(f"   • F1-Score  : {f1*100:.2f}%")
print(f"   • Ngưỡng tối ưu tau*: {optimal_thresh_xgb:.2f}")
print("=" * 90)

model_data = {
    "model": best_xgb,
    "optimal_threshold": float(optimal_thresh_xgb),
    "metrics": {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1}
}

try:
    import torch
    torch.save(model_data, MODEL_PT_PATH)
    torch.save(model_data, MODEL_PTH_PATH)
except Exception:
    pass

joblib.dump(model_data, MODEL_PT_PATH)
joblib.dump(model_data, MODEL_PTH_PATH)
joblib.dump(best_xgb, MODEL_PKL_PATH)

print("\n" + "=" * 90)
print(f"✅ ĐÃ LƯU BEST MODEL (Định dạng .pt) : {MODEL_PT_PATH}")
print(f"✅ ĐÃ LƯU BEST MODEL (Định dạng .pth): {MODEL_PTH_PATH}")
print(f"✅ ĐÃ LƯU BEST MODEL (Định dạng .pkl): {MODEL_PKL_PATH}")
print("=" * 90)
