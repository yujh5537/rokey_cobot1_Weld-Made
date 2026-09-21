package com.weldmade.backend.workorder.repository;

import com.weldmade.backend.workorder.entity.WorkOrder;
import org.springframework.data.repository.Repository;

import java.util.List;
import java.util.Optional;

public interface WorkOrderRepository extends Repository<WorkOrder, String> {

    List<WorkOrder> findAllByOrderByCreatedAtDesc();

    Optional<WorkOrder> findById(String workOrderId);

    List<WorkOrder> findByWorkpieceIdOrderByCreatedAtDesc(
            String workpieceId
    );

    WorkOrder save(WorkOrder workOrder);

    boolean existsById(String workOrderId);
}