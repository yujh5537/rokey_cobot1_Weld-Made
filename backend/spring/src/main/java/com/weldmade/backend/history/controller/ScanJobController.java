package com.weldmade.backend.history.controller;

import com.weldmade.backend.history.entity.ScanJob;
import com.weldmade.backend.history.service.ScanJobService;
import com.weldmade.backend.history.dto.ScanHistoryDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/history/scans")
public class ScanJobController {

    private final ScanJobService scanJobService;

    public ScanJobController(ScanJobService scanJobService) {
        this.scanJobService = scanJobService;
    }

    @GetMapping
    public List<ScanJob> getScanJobs() {
        return scanJobService.getScanJobs();
    }

    @GetMapping("/{scanId}")
    public ResponseEntity<ScanHistoryDetail> getScanJob(
            @PathVariable String scanId
    ) {
        return scanJobService.getScanHistoryDetail(scanId)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }
}