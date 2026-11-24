-- Các bảng app tạo thêm trong corpus.db. Bảng `articles` có sẵn, không tạo ở đây.
-- Chạy nhiều lần không sao (create table if not exists).

-- p01 (kyc_v3): kết quả quét công ty trong bài
create table if not exists article_scan_v3 (
    article_id integer primary key,
    n_company  integer,
    scanned_at text
);
create table if not exists article_company_v3 (
    article_id integer,
    ticker     text,
    n_mention  integer,
    primary key (article_id, ticker)
);
create table if not exists chunk_vectors_v3 (
    article_id integer,
    chunk_no   integer,
    vec        blob,
    primary key (article_id, chunk_no)
);

-- p02: truy xuất bằng chứng
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
create table if not exists ce_scores_v3 (
    ticker     text,
    article_id integer,
    score      real,
    primary key (ticker, article_id)
);

-- p03: LLM đọc bài
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
    run_id       integer primary key,
    n_read       integer,
    n_risk       integer,
    n_error      integer,
    ty_le_khop   real,
    created_at   text
);

-- p04: báo cáo
create table if not exists reports (
    run_id     integer primary key,
    ticker     text,
    n_events   integer,
    report_md  text,
    detail     text,
    created_at text
);

-- Mới: nhãn ER của job nền (bài nào nhắc đúng công ty nào)
create table if not exists er_labels (
    article_id integer,
    ticker     text,
    score      real,      -- xác suất đúng là công ty này
    label      integer,   -- 1 nếu score >= ngưỡng
    model      text,
    created_at text,
    score_lr   real,      -- điểm của mô hình LR
    nguon      text,      -- lr: nhãn của LR | cho_llm: đang chờ LLM xem lại (tạm gắn 1) | llm: nhãn của LLM
    primary key (article_id, ticker, model)
);

-- Mới: mỗi lần LLM xem lại một cặp (ER nền), hỏi nhiều lần rồi lấy trung bình
create table if not exists llm_labels (
    article_id     integer,
    ticker         text,
    prompt_version text,
    lan            integer,   -- lần hỏi thứ mấy
    nhan           integer,
    tu_tin         real,
    diem           real,      -- xác suất nhãn 1: tu_tin nếu nhãn 1, ngược lại 1 - tu_tin
    ly_do          text,
    model          text,
    created_at     text,
    primary key (article_id, ticker, prompt_version, lan)
);

-- Mới: công việc chạy nền (screening, er_background)
create table if not exists jobs (
    job_id     integer primary key autoincrement,
    kind       text,      -- screening | er_background
    ticker     text,
    status     text,      -- queued | running | done | error
    step       text,      -- bước đang chạy, hiện ở StatusBanner
    run_id     integer,   -- run_id của screening_runs khi xong
    error      text,
    created_at text,
    updated_at text
);
