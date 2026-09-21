package com.weldmade.backend.history.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

@Entity
@Table(name = "scan_jobs")
public class ScanJob {

    @Id
    @Column(name = "scan_id", nullable = false)
    private String scanId;

    @Column(name = "success")
    private Boolean success;

    @Column(name = "reason_code")
    private Integer reasonCode;

    @Column(name = "reason")
    private String reason;

    @Column(name = "detail")
    private String detail;

    @Column(name = "frame_id")
    private String frameId;

    @Column(name = "started_at_ms")
    private Long startedAtMs;

    @Column(name = "finished_at_ms")
    private Long finishedAtMs;

    @Column(name = "published_at_ms")
    private Long publishedAtMs;

    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;

    protected ScanJob() {
    }

    public String getScanId() {
        return scanId;
    }

    public Boolean getSuccess() {
        return success;
    }

    public Integer getReasonCode() {
        return reasonCode;
    }

    public String getReason() {
        return reason;
    }

    public String getDetail() {
        return detail;
    }

    public String getFrameId() {
        return frameId;
    }

    public Long getStartedAtMs() {
        return startedAtMs;
    }

    public Long getFinishedAtMs() {
        return finishedAtMs;
    }

    public Long getPublishedAtMs() {
        return publishedAtMs;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}