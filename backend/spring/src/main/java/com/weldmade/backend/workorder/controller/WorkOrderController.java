package com.weldmade.backend.workorder.controller;

import com.weldmade.backend.workorder.entity.WorkOrder;
import com.weldmade.backend.workorder.service.WorkOrderService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/work-orders")
public class WorkOrderController {

    private final WorkOrderService workOrderService;

    public WorkOrderController(
            WorkOrderService workOrderService
    ) {
        this.workOrderService = workOrderService;
    }

    @GetMapping
    public List<WorkOrder> getWorkOrders() {
        return workOrderService.getWorkOrders();
    }

    @GetMapping("/{workOrderId}")
    public ResponseEntity<WorkOrder> getWorkOrder(
            @PathVariable String workOrderId
    ) {
        return workOrderService.getWorkOrder(workOrderId)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @GetMapping("/by-workpiece/{workpieceId}")
    public List<WorkOrder> getWorkOrdersByWorkpiece(
            @PathVariable String workpieceId
    ) {
        return workOrderService.getWorkOrdersByWorkpiece(workpieceId);
    }

    @PostMapping
    public ResponseEntity<WorkOrder> createWorkOrder(
            @RequestBody CreateWorkOrderRequest request
    ) {
        if (request.workOrderId() == null
                || request.workOrderId().isBlank()
                || request.workpieceId() == null
                || request.workpieceId().isBlank()
                || request.name() == null
                || request.name().isBlank()) {

            return ResponseEntity
                    .badRequest()
                    .build();
        }

        try {
            WorkOrder workOrder = workOrderService.createWorkOrder(
                    request.workOrderId(),
                    request.workpieceId(),
                    request.name(),
                    request.note()
            );

            return ResponseEntity
                    .status(HttpStatus.CREATED)
                    .body(workOrder);

        } catch (IllegalArgumentException exception) {
            return ResponseEntity
                    .status(HttpStatus.CONFLICT)
                    .build();
        }
    }

    @PutMapping("/{workOrderId}")
    public ResponseEntity<WorkOrder> updateWorkOrder(
            @PathVariable String workOrderId,
            @RequestBody UpdateWorkOrderRequest request
    ) {
        if (request.name() == null || request.name().isBlank()) {
            return ResponseEntity
                    .badRequest()
                    .build();
        }

        return workOrderService.updateWorkOrder(
                        workOrderId,
                        request.name(),
                        request.status(),
                        request.note()
                )
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    public record CreateWorkOrderRequest(
            String workOrderId,
            String workpieceId,
            String name,
            String note
    ) {
    }

    public record UpdateWorkOrderRequest(
            String name,
            String status,
            String note
    ) {
    }
}