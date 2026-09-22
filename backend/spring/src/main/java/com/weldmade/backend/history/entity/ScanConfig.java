package com.weldmade.backend.history.entity;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;

@Entity
@Table(name = "scan_configs")
public class ScanConfig {

    @Id
    @Column(name = "scan_id", nullable = false)
    private String scanId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "config", nullable = false, columnDefinition = "jsonb")
    private JsonNode config;

    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;

    protected ScanConfig() {
    }

    public String getScanId() {
        return scanId;
    }

    public JsonNode getConfig() {
        return config;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}