package com.weldmade.backend.workorder.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

@Entity
@Table(name = "work_orders")
public class WorkOrder {

    @Id
    @Column(name = "work_order_id", nullable = false)
    private String workOrderId;

    @Column(name = "workpiece_id", nullable = false)
    private String workpieceId;

    @Column(name = "name", nullable = false)
    private String name;

    @Column(name = "status", nullable = false)
    private String status = "READY";

    @Column(name = "note")
    private String note;

    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    protected WorkOrder() {
    }

    public WorkOrder(
            String workOrderId,
            String workpieceId,
            String name,
            String note
    ) {
        this.workOrderId = workOrderId;
        this.workpieceId = workpieceId;
        this.name = name;
        this.note = note;
        this.status = "READY";
    }

    @PrePersist
    protected void onCreate() {
        OffsetDateTime now = OffsetDateTime.now();

        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = OffsetDateTime.now();
    }

    public void update(
            String name,
            String status,
            String note
    ) {
        this.name = name;
        this.status = status;
        this.note = note;
    }

    public String getWorkOrderId() {
        return workOrderId;
    }

    public String getWorkpieceId() {
        return workpieceId;
    }

    public String getName() {
        return name;
    }

    public String getStatus() {
        return status;
    }

    public String getNote() {
        return note;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}