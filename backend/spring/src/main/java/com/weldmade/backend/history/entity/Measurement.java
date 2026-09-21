package com.weldmade.backend.history.entity;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;

@Entity
@Table(name = "measurements")
public class Measurement {

    @Id
    @Column(name = "scan_id", nullable = false)
    private String scanId;

    @Column(name = "stamp_ms", nullable = false)
    private long stampMs;

    @Column(name = "z_top_mm")
    private Double zTopMm;

    @Column(name = "z_top_valid", nullable = false)
    private boolean zTopValid;

    @Column(name = "x_pos_mm")
    private Double xPosMm;

    @Column(name = "x_pos_valid", nullable = false)
    private boolean xPosValid;

    @Column(name = "x_neg_mm")
    private Double xNegMm;

    @Column(name = "x_neg_valid", nullable = false)
    private boolean xNegValid;

    @Column(name = "y_pos_mm")
    private Double yPosMm;

    @Column(name = "y_pos_valid", nullable = false)
    private boolean yPosValid;

    @Column(name = "y_neg_mm")
    private Double yNegMm;

    @Column(name = "y_neg_valid", nullable = false)
    private boolean yNegValid;

    @Column(name = "width_mm")
    private Double widthMm;

    @Column(name = "length_mm")
    private Double lengthMm;

    @Column(name = "height_mm")
    private Double heightMm;

    @Column(name = "dims_valid", nullable = false)
    private boolean dimsValid;

    @Column(name = "support_z_mm")
    private Double supportZMm;

    @Column(name = "support_z_valid", nullable = false)
    private boolean supportZValid;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "vertices", columnDefinition = "jsonb")
    private JsonNode vertices;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "edges", columnDefinition = "jsonb")
    private JsonNode edges;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "path_candidates", columnDefinition = "jsonb")
    private JsonNode pathCandidates;

    @Column(name = "box_valid", nullable = false)
    private boolean boxValid;

        @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;

    protected Measurement() {
    }

    public String getScanId() {
        return scanId;
    }

    public long getStampMs() {
        return stampMs;
    }

    @JsonProperty("zTopMm")
    public Double getZTopMm() {
        return zTopMm;
    }

    @JsonProperty("zTopValid")
    public boolean isZTopValid() {
        return zTopValid;
    }

    @JsonProperty("xPosMm")
    public Double getXPosMm() {
        return xPosMm;
    }

    @JsonProperty("xPosValid")
    public boolean isXPosValid() {
        return xPosValid;
    }

    @JsonProperty("xNegMm")
    public Double getXNegMm() {
        return xNegMm;
    }

    @JsonProperty("xNegValid")
    public boolean isXNegValid() {
        return xNegValid;
    }

    @JsonProperty("yPosMm")
    public Double getYPosMm() {
        return yPosMm;
    }

    @JsonProperty("yPosValid")
    public boolean isYPosValid() {
        return yPosValid;
    }

    @JsonProperty("yNegMm")
    public Double getYNegMm() {
        return yNegMm;
    }

    @JsonProperty("yNegValid")
    public boolean isYNegValid() {
        return yNegValid;
    }

    public Double getWidthMm() {
        return widthMm;
    }

    public Double getLengthMm() {
        return lengthMm;
    }

    public Double getHeightMm() {
        return heightMm;
    }

    public boolean isDimsValid() {
        return dimsValid;
    }

    public Double getSupportZMm() {
        return supportZMm;
    }

    public boolean isSupportZValid() {
        return supportZValid;
    }

    public JsonNode getVertices() {
        return vertices;
    }

    public JsonNode getEdges() {
        return edges;
    }

    public JsonNode getPathCandidates() {
        return pathCandidates;
    }

    public boolean isBoxValid() {
        return boxValid;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}