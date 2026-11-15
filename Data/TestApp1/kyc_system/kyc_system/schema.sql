-- Các bảng hệ thống tạo trong corpus.db. Bảng articles do crawler quản lý.

-- Entity Resolution
create table if not exists er_scan (
    article_id    integer primary key,
    content_hash  text,
    n_mention     integer,
    n_company     integer,      -- số công ty được ER xác nhận (quyết định 1)
    rule_version  text,
    model_version text,
    scanned_at    text
);

create table if not exists er_mentions (
    article_id    integer,
    ticker        text,
    alias         text,
    chuoi_khop    text,
    loai_alias    text,
    start_pos     integer,      -- vị trí trên chuỗi chuan_hoa(title + "\n" + cleaned_text), tính từ 0
    end_pos       integer,
    trong_tieu_de integer,
    ten_dai_hon   text,
    luat_loai_tru text,
    sach          integer
);
create index if not exists idx_er_mentions_article on er_mentions(article_id);

create table if not exists er_article_company (
    article_id      integer,
    ticker          text,
    f1_alias        integer,
    f2_ma_ck        integer,
    f3_lanh_dao     integer,
    f4_dia_ly       integer,
    f6_ty_le_loai   real,
    f7_tieu_de      integer,
    f8_so_nhac_sach integer,
    chi_alias_yeu   integer,
    xac_suat        real,
    quyet_dinh      text,       -- 1 / 0 / xem
    model_version   text,
    created_at      text,
    primary key (article_id, ticker)
);
create index if not exists idx_er_pair_ticker on er_article_company(ticker, quyet_dinh);

-- Vector bge-m3, mỗi đoạn 200 từ (giữ nguyên định dạng của prod_01)
create table if not exists chunk_vectors (
    article_id integer,
    chunk_no   integer,
    vec        blob,
    primary key (article_id, chunk_no)
);

-- Truy xuất (giữ nguyên định dạng của prod_02)
create table if not exists screening_runs (
    run_id     integer primary key autoincrement,
    ticker     text,
    created_at text,
    date_from  text,
    n_mention  integer,
    n_bm25     integer,
    n_top      integer,
    config     text
);

create table if not exists run_results (
    run_id     integer,
    rank       integer,
    article_id integer,
    bm25_rank  integer,
    dense_rank integer,
    ce_score   real,
    final      real,
    primary key (run_id, rank)
);

create table if not exists ce_scores (
    ticker     text,
    article_id integer,
    score      real,
    primary key (ticker, article_id)
);

-- LLM đọc bài (giữ nguyên định dạng của prod_03)
create table if not exists llm_reads (
    ticker         text,
    article_id     integer,
    prompt_version text,
    model          text,
    lien_quan      integer,
    result         text,
    trich_dan_khop integer,
    created_at     text,
    primary key (ticker, article_id, prompt_version)
);

create table if not exists run_llm (
    run_id     integer primary key,
    n_read     integer,
    n_risk     integer,
    n_error    integer,
    ty_le_khop real,
    created_at text
);

-- Báo cáo (giữ nguyên định dạng của prod_04)
create table if not exists reports (
    run_id     integer primary key,
    ticker     text,
    n_events   integer,
    report_md  text,
    detail     text,
    created_at text
);
