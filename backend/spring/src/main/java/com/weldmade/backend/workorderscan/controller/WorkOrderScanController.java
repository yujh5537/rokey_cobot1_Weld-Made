package com.weldmade.backend.workorderscan.controller;

import com.weldmade.backend.workorderscan.entity.WorkOrderScan;
import com.weldmade.backend.workorderscan.service.WorkOrderScanService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.NoSuchElementException;

@RestController
@RequestMapping("/api/work-orders/{workOrderId}/scans")
public class WorkOrderScanController {

    private final WorkOrderScanService workOrderScanService;

    public WorkOrderScanController(
            WorkOrderScanService workOrderScanService
    ) {
        this.workOrderScanService = workOrderScanService;
    }

    @GetMapping
    public List<WorkOrderScan> getScansByWorkOrder(
            @PathVariable String workOrderId
    ) {
        return workOrderScanService.getScansByWorkOrder(workOrderId);
    }

    @PostMapping("/{scanId}")
    public ResponseEntity<WorkOrderScan> linkScan(
            @PathVariable String workOrderId,
            @PathVariable String scanId
    ) {
        try {
            WorkOrderScan workOrderScan =
                    workOrderScanService.linkScan(
                            workOrderId,
                            scanId
                    );

            return ResponseEntity
                    .status(HttpStatus.CREATED)
                    .body(workOrderScan);

        } catch (NoSuchElementException exception) {
            return ResponseEntity
                    .notFound()
                    .build();

        } catch (IllegalStateException exception) {
            return ResponseEntity
                    .status(HttpStatus.CONFLICT)
                    .build();
        }
    }
}