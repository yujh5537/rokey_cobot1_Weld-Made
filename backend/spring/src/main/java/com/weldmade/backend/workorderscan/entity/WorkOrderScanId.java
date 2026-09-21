package com.weldmade.backend.workorderscan.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;

import java.io.Serializable;
import java.util.Objects;

@Embeddable
public class WorkOrderScanId implements Serializable {

    @Column(name = "work_order_id", nullable = false)
    private String workOrderId;

    @Column(name = "scan_id", nullable = false)
    private String scanId;

    protected WorkOrderScanId() {
    }

    public WorkOrderScanId(
            String workOrderId,
            String scanId
    ) {
        this.workOrderId = workOrderId;
        this.scanId = scanId;
    }

    public String getWorkOrderId() {
        return workOrderId;
    }

    public String getScanId() {
        return scanId;
    }

    @Override
    public boolean equals(Object object) {
        if (this == object) {
            return true;
        }

        if (!(object instanceof WorkOrderScanId other)) {
            return false;
        }

        return Objects.equals(workOrderId, other.workOrderId)
                && Objects.equals(scanId, other.scanId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(workOrderId, scanId);
    }
}