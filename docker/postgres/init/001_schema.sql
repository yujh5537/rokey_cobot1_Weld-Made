-- =========================================================
-- T28 PostgreSQL schema
-- =========================================================

-- 1. 스캔 작업
CREATE TABLE IF NOT EXISTS scan_jobs (
    scan_id TEXT PRIMARY KEY,

    success BOOLEAN,
    reason_code INTEGER,
    reason TEXT,
    detail TEXT,
    frame_id TEXT,

    started_at_ms BIGINT,
    finished_at_ms BIGINT,
    published_at_ms BIGINT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- 2. 측정 결과
CREATE TABLE IF NOT EXISTS measurements (
    scan_id TEXT PRIMARY KEY
        REFERENCES scan_jobs(scan_id)
        ON DELETE CASCADE,

    stamp_ms BIGINT NOT NULL,

    z_top_mm DOUBLE PRECISION,
    z_top_valid BOOLEAN NOT NULL DEFAULT FALSE,

    x_pos_mm DOUBLE PRECISION,
    x_pos_valid BOOLEAN NOT NULL DEFAULT FALSE,

    x_neg_mm DOUBLE PRECISION,
    x_neg_valid BOOLEAN NOT NULL DEFAULT FALSE,

    y_pos_mm DOUBLE PRECISION,
    y_pos_valid BOOLEAN NOT NULL DEFAULT FALSE,

    y_neg_mm DOUBLE PRECISION,
    y_neg_valid BOOLEAN NOT NULL DEFAULT FALSE,

    width_mm DOUBLE PRECISION,
    length_mm DOUBLE PRECISION,
    height_mm DOUBLE PRECISION,
    dims_valid BOOLEAN NOT NULL DEFAULT FALSE,

    support_z_mm DOUBLE PRECISION,
    support_z_valid BOOLEAN NOT NULL DEFAULT FALSE,

    vertices JSONB,
    edges JSONB,
    path_candidates JSONB,
    box_valid BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- 3. 접촉 / 엣지 이벤트
CREATE TABLE IF NOT EXISTS contact_events (
    id BIGSERIAL PRIMARY KEY,

    scan_id TEXT NOT NULL,
    event_id BIGINT NOT NULL,
    motion_id BIGINT,
    sample_id BIGINT,

    event_type TEXT NOT NULL,
    source TEXT,
    frame_id TEXT,

    pose JSONB,
    wrench JSONB,

    pose_stamp_ms BIGINT,
    force_stamp_ms BIGINT,
    detect_stamp_ms BIGINT,

    force_delta_n DOUBLE PRECISION,

    z_drop_mm DOUBLE PRECISION,
    z_drop_valid BOOLEAN NOT NULL DEFAULT FALSE,

    debounce_count INTEGER,
    published_at_ms BIGINT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (scan_id, event_id)
);


-- 4. 스캔에 실제 적용된 설정
CREATE TABLE IF NOT EXISTS scan_configs (
    scan_id TEXT PRIMARY KEY
        REFERENCES scan_jobs(scan_id)
        ON DELETE CASCADE,

    config JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);