package com.weldmade.backend.workorderscan.repository;

import com.weldmade.backend.workorderscan.entity.WorkOrderScan;
import com.weldmade.backend.workorderscan.entity.WorkOrderScanId;
import org.springframework.data.repository.Repository;

import java.util.List;
import java.util.Optional;

public interface WorkOrderScanRepository
        extends Repository<WorkOrderScan, WorkOrderScanId> {

    WorkOrderScan save(WorkOrderScan workOrderScan);

    List<WorkOrderScan> findById_WorkOrderIdOrderByLinkedAtDesc(
            String workOrderId
    );

    Optional<WorkOrderScan> findById_ScanId(
            String scanId
    );

    boolean existsById(WorkOrderScanId id);
}