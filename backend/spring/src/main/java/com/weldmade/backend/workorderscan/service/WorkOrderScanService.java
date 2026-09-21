package com.weldmade.backend.workorderscan.service;

import com.weldmade.backend.history.repository.ScanJobRepository;
import com.weldmade.backend.workorder.repository.WorkOrderRepository;
import com.weldmade.backend.workorderscan.entity.WorkOrderScan;
import com.weldmade.backend.workorderscan.repository.WorkOrderScanRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.NoSuchElementException;

@Service
public class WorkOrderScanService {

    private final WorkOrderScanRepository workOrderScanRepository;
    private final WorkOrderRepository workOrderRepository;
    private final ScanJobRepository scanJobRepository;

    public WorkOrderScanService(
            WorkOrderScanRepository workOrderScanRepository,
            WorkOrderRepository workOrderRepository,
            ScanJobRepository scanJobRepository
    ) {
        this.workOrderScanRepository = workOrderScanRepository;
        this.workOrderRepository = workOrderRepository;
        this.scanJobRepository = scanJobRepository;
    }

    @Transactional(readOnly = true)
    public List<WorkOrderScan> getScansByWorkOrder(
            String workOrderId
    ) {
        return workOrderScanRepository
                .findById_WorkOrderIdOrderByLinkedAtDesc(workOrderId);
    }

    @Transactional
    public WorkOrderScan linkScan(
            String workOrderId,
            String scanId
    ) {
        if (workOrderRepository.findById(workOrderId).isEmpty()) {
            throw new NoSuchElementException(
                    "Work order does not exist: " + workOrderId
            );
        }

        if (scanJobRepository.findById(scanId).isEmpty()) {
            throw new NoSuchElementException(
                    "Scan does not exist: " + scanId
            );
        }

        if (workOrderScanRepository.findById_ScanId(scanId).isPresent()) {
            throw new IllegalStateException(
                    "Scan is already linked: " + scanId
            );
        }

        WorkOrderScan workOrderScan = new WorkOrderScan(
                workOrderId,
                scanId
        );

        return workOrderScanRepository.save(workOrderScan);
    }
}