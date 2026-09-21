package com.weldmade.backend.workorderscan.entity;

import jakarta.persistence.Column;
import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

@Entity
@Table(name = "work_order_scans")
public class WorkOrderScan {

    @EmbeddedId
    private WorkOrderScanId id;

    @Column(name = "linked_at", nullable = false)
    private OffsetDateTime linkedAt;

    protected WorkOrderScan() {
    }

    public WorkOrderScan(
            String workOrderId,
            String scanId
    ) {
        this.id = new WorkOrderScanId(
                workOrderId,
                scanId
        );
    }

    @PrePersist
    protected void onCreate() {
        linkedAt = OffsetDateTime.now();
    }

    public WorkOrderScanId getId() {
        return id;
    }

    public String getWorkOrderId() {
        return id.getWorkOrderId();
    }

    public String getScanId() {
        return id.getScanId();
    }

    public OffsetDateTime getLinkedAt() {
        return linkedAt;
    }
}