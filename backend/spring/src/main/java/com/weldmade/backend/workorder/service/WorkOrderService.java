package com.weldmade.backend.workorder.service;

import com.weldmade.backend.workorder.entity.WorkOrder;
import com.weldmade.backend.workorder.repository.WorkOrderRepository;
import com.weldmade.backend.workpiece.repository.WorkpieceRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
public class WorkOrderService {

    private final WorkOrderRepository workOrderRepository;
    private final WorkpieceRepository workpieceRepository;

    public WorkOrderService(
            WorkOrderRepository workOrderRepository,
            WorkpieceRepository workpieceRepository
    ) {
        this.workOrderRepository = workOrderRepository;
        this.workpieceRepository = workpieceRepository;
    }

    @Transactional(readOnly = true)
    public List<WorkOrder> getWorkOrders() {
        return workOrderRepository.findAllByOrderByCreatedAtDesc();
    }

    @Transactional(readOnly = true)
    public Optional<WorkOrder> getWorkOrder(String workOrderId) {
        return workOrderRepository.findById(workOrderId);
    }

    @Transactional(readOnly = true)
    public List<WorkOrder> getWorkOrdersByWorkpiece(
            String workpieceId
    ) {
        return workOrderRepository
                .findByWorkpieceIdOrderByCreatedAtDesc(workpieceId);
    }

    @Transactional
    public WorkOrder createWorkOrder(
            String workOrderId,
            String workpieceId,
            String name,
            String note
    ) {
        if (!workpieceRepository.existsById(workpieceId)) {
            throw new IllegalArgumentException(
                    "Workpiece does not exist: " + workpieceId
            );
        }

        if (workOrderRepository.existsById(workOrderId)) {
            throw new IllegalArgumentException(
                    "Work order already exists: " + workOrderId
            );
        }

        WorkOrder workOrder = new WorkOrder(
                workOrderId,
                workpieceId,
                name,
                note
        );

        return workOrderRepository.save(workOrder);
    }

    @Transactional
    public Optional<WorkOrder> updateWorkOrder(
            String workOrderId,
            String name,
            String status,
            String note
    ) {
        return workOrderRepository.findById(workOrderId)
                .map(workOrder -> {
                    workOrder.update(
                            name,
                            status,
                            note
                    );

                    return workOrderRepository.save(workOrder);
                });
    }
}