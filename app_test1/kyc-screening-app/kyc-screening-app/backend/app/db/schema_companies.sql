-- Các bảng app dùng trong companies.db. Bảng `companies` (crawl thô) và `company_names` có sẵn, không tạo ở đây.
-- Chạy nhiều lần không sao (if not exists).

-- Hồ sơ đã chọn lọc, mỗi ticker một dòng
create table if not exists company_profiles (
    ticker            text primary key,
    tax_id            text,
    company_name      text,
    key_leaders       text,
    address           text,
    industry          text,
    industry_keywords text,
    website           text,
    updated_at        text
);

-- Thành viên rổ chỉ số. Rổ thay đổi thì thêm dòng với ngày mới, không tạo bảng mới.
create table if not exists index_members (
    ten_chi_so    text,      -- VN100
    ticker        text,
    ngay_hieu_luc text,      -- yyyy-mm-dd
    primary key (ten_chi_so, ticker, ngay_hieu_luc)
);

-- Danh mục VN100 mới nhất, cùng cột với bảng snapshot cũ (vn100_20261106)
create view if not exists vn100 as
select p.ticker, p.tax_id, p.company_name, n.short_name, p.key_leaders, p.address,
       p.industry, p.industry_keywords, p.website
from index_members m
join company_profiles p on p.ticker = m.ticker
left join company_names n on n.ticker = m.ticker
where m.ten_chi_so = 'VN100'
  and m.ngay_hieu_luc = (select max(ngay_hieu_luc) from index_members where ten_chi_so = 'VN100');

-- Log tra cứu (input): mỗi tên được tra một dòng
create table if not exists lookup_queries (
    query_id        integer primary key autoincrement,
    created_at      text,
    doan            text,      -- đoạn văn người dùng nhập
    ten             text,      -- tên được tra trong đoạn
    trang_thai      text,      -- duy_nhat | can_xac_nhan | khong_co
    model           text,      -- phiên bản mô hình đã dùng
    thoi_gian_ms    integer,
    ticker_xac_nhan text,      -- analyst chọn ở màn hình xác nhận; 'khong_phai' nếu bác cả danh sách
    xac_nhan_luc    text
);

-- Ứng viên của mỗi lần tra cứu, giữ điểm để sau này tính lại khi đổi ngưỡng
create table if not exists lookup_candidates (
    query_id       integer,
    hang           integer,
    ticker         text,
    diem           real,
    co_mst         integer,
    khop_chinh_xac integer,
    primary key (query_id, hang)
);
