import os

import psycopg
from psycopg.types.json import Jsonb



# =========================================================
# PostgreSQL 설정
# =========================================================

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "contact_scan")
DB_USER = os.getenv("POSTGRES_USER", "contact_scan")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


def get_db_connection():
    """
    PostgreSQL 연결을 생성한다.

    실제 commit / rollback은 이 연결을 사용하는
    with 블록에서 관리한다.
    """

    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

def to_jsonb(value):
    """
    Python dict/list를 PostgreSQL JSONB로 변환한다.

    None은 JSON null이 아니라
    PostgreSQL NULL로 저장한다.
    """

    if value is None:
        return None

    return Jsonb(value)


def save_scan_result(payload: dict):
    """
    MQTT scan/result payload를 PostgreSQL에 저장한다.

    하나의 transaction 안에서:
    1. scan_jobs
    2. measurements
    3. scan_configs

    세 테이블을 함께 저장한다.
    """

    scan_id = payload["scan_id"]

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            # -------------------------------------------------
            # 1. 스캔 작업 저장
            # -------------------------------------------------

            cursor.execute(
                """
                INSERT INTO scan_jobs (
                    scan_id,
                    success,
                    reason_code,
                    reason,
                    detail,
                    frame_id,
                    started_at_ms,
                    finished_at_ms,
                    published_at_ms
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (scan_id)
                DO UPDATE SET
                    success = EXCLUDED.success,
                    reason_code = EXCLUDED.reason_code,
                    reason = EXCLUDED.reason,
                    detail = EXCLUDED.detail,
                    frame_id = EXCLUDED.frame_id,
                    started_at_ms = EXCLUDED.started_at_ms,
                    finished_at_ms = EXCLUDED.finished_at_ms,
                    published_at_ms = EXCLUDED.published_at_ms
                """,
                (
                    scan_id,
                    payload["success"],
                    payload["reason_code"],
                    payload["reason"],
                    payload["detail"],
                    payload["frame_id"],
                    payload["started_at_ms"],
                    payload["finished_at_ms"],
                    payload["published_at_ms"],
                ),
            )

            # -------------------------------------------------
            # 2. 측정 결과 저장
            # -------------------------------------------------

            cursor.execute(
                """
                INSERT INTO measurements (
                    scan_id,
                    stamp_ms,

                    z_top_mm,
                    z_top_valid,

                    x_pos_mm,
                    x_pos_valid,

                    x_neg_mm,
                    x_neg_valid,

                    y_pos_mm,
                    y_pos_valid,

                    y_neg_mm,
                    y_neg_valid,

                    width_mm,
                    length_mm,
                    height_mm,
                    dims_valid,

                    support_z_mm,
                    support_z_valid,

                    vertices,
                    edges,
                    path_candidates,
                    box_valid
                )
                VALUES (
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (scan_id)
                DO UPDATE SET
                    stamp_ms = EXCLUDED.stamp_ms,

                    z_top_mm = EXCLUDED.z_top_mm,
                    z_top_valid = EXCLUDED.z_top_valid,

                    x_pos_mm = EXCLUDED.x_pos_mm,
                    x_pos_valid = EXCLUDED.x_pos_valid,

                    x_neg_mm = EXCLUDED.x_neg_mm,
                    x_neg_valid = EXCLUDED.x_neg_valid,

                    y_pos_mm = EXCLUDED.y_pos_mm,
                    y_pos_valid = EXCLUDED.y_pos_valid,

                    y_neg_mm = EXCLUDED.y_neg_mm,
                    y_neg_valid = EXCLUDED.y_neg_valid,

                    width_mm = EXCLUDED.width_mm,
                    length_mm = EXCLUDED.length_mm,
                    height_mm = EXCLUDED.height_mm,
                    dims_valid = EXCLUDED.dims_valid,

                    support_z_mm = EXCLUDED.support_z_mm,
                    support_z_valid = EXCLUDED.support_z_valid,

                    vertices = EXCLUDED.vertices,
                    edges = EXCLUDED.edges,
                    path_candidates = EXCLUDED.path_candidates,
                    box_valid = EXCLUDED.box_valid
                """,
                (
                    scan_id,
                    payload["stamp_ms"],

                    payload["z_top_mm"],
                    payload["z_top_valid"],

                    payload["x_pos_mm"],
                    payload["x_pos_valid"],

                    payload["x_neg_mm"],
                    payload["x_neg_valid"],

                    payload["y_pos_mm"],
                    payload["y_pos_valid"],

                    payload["y_neg_mm"],
                    payload["y_neg_valid"],

                    payload["width_mm"],
                    payload["length_mm"],
                    payload["height_mm"],
                    payload["dims_valid"],

                    payload["support_z_mm"],
                    payload["support_z_valid"],

                    to_jsonb(payload["vertices"]),
                    to_jsonb(payload["edges"]),
                    to_jsonb(payload["path_candidates"]),
                    payload["box_valid"],
                ),
            )

            # -------------------------------------------------
            # 3. 해당 스캔에 적용된 설정 저장
            # -------------------------------------------------

            cursor.execute(
                """
                INSERT INTO scan_configs (
                    scan_id,
                    config
                )
                VALUES (
                    %s, %s
                )
                ON CONFLICT (scan_id)
                DO UPDATE SET
                    config = EXCLUDED.config
                """,
                (
                    scan_id,
                    Jsonb(payload["config"]),
                ),
            )

    return scan_id

def save_contact_event(payload: dict):
    """
    MQTT contact/event payload를 PostgreSQL에 저장한다.

    같은 scan_id + event_id가 다시 들어오면
    기존 이벤트 내용을 최신 값으로 갱신한다.
    """

    scan_id = payload["scan_id"]
    event_id = payload["event_id"]

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO contact_events (
                    scan_id,
                    event_id,
                    motion_id,
                    sample_id,
                    event_type,
                    source,
                    frame_id,
                    pose,
                    wrench,
                    pose_stamp_ms,
                    force_stamp_ms,
                    detect_stamp_ms,
                    force_delta_n,
                    z_drop_mm,
                    z_drop_valid,
                    debounce_count,
                    published_at_ms
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s,
                    %s, %s,
                    %s,
                    %s
                )
                ON CONFLICT (scan_id, event_id)
                DO UPDATE SET
                    motion_id = EXCLUDED.motion_id,
                    sample_id = EXCLUDED.sample_id,
                    event_type = EXCLUDED.event_type,
                    source = EXCLUDED.source,
                    frame_id = EXCLUDED.frame_id,
                    pose = EXCLUDED.pose,
                    wrench = EXCLUDED.wrench,
                    pose_stamp_ms = EXCLUDED.pose_stamp_ms,
                    force_stamp_ms = EXCLUDED.force_stamp_ms,
                    detect_stamp_ms = EXCLUDED.detect_stamp_ms,
                    force_delta_n = EXCLUDED.force_delta_n,
                    z_drop_mm = EXCLUDED.z_drop_mm,
                    z_drop_valid = EXCLUDED.z_drop_valid,
                    debounce_count = EXCLUDED.debounce_count,
                    published_at_ms = EXCLUDED.published_at_ms
                """,
                (
                    scan_id,
                    event_id,
                    payload["motion_id"],
                    payload["sample_id"],
                    payload["type"],
                    payload["source"],
                    payload["frame_id"],
                    to_jsonb(payload["pose"]),
                    to_jsonb(payload["wrench"]),
                    payload["pose_stamp_ms"],
                    payload["force_stamp_ms"],
                    payload["detect_stamp_ms"],
                    payload["force_delta_n"],
                    payload["z_drop_mm"],
                    payload["z_drop_valid"],
                    payload["debounce_count"],
                    payload["published_at_ms"],
                ),
            )

    return event_id