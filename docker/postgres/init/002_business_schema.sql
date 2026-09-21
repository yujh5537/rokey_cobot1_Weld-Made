-- =========================================================
-- T35 Spring Boot business schema
-- =========================================================

-- 1. 공작물
CREATE TABLE IF NOT EXISTS workpieces (
    workpiece_id TEXT PRIMARY KEY,

    name TEXT NOT NULL,
    description TEXT,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- 2. 작업
CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id TEXT PRIMARY KEY,

    workpiece_id TEXT NOT NULL
        REFERENCES workpieces(workpiece_id)
        ON DELETE RESTRICT,

    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'READY',
    note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- 3. 작업과 실제 스캔 결과 연결
CREATE TABLE IF NOT EXISTS work_order_scans (
    work_order_id TEXT NOT NULL
        REFERENCES work_orders(work_order_id)
        ON DELETE CASCADE,

    scan_id TEXT NOT NULL UNIQUE
        REFERENCES scan_jobs(scan_id)
        ON DELETE CASCADE,

    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (work_order_id, scan_id)
);