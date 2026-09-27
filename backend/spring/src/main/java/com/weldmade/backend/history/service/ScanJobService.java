package com.weldmade.backend.history.service;

import com.weldmade.backend.history.dto.ScanHistoryDetail;
import com.weldmade.backend.history.entity.Measurement;
import com.weldmade.backend.history.entity.ScanConfig;
import com.weldmade.backend.history.entity.ScanJob;
import com.weldmade.backend.history.repository.MeasurementRepository;
import com.weldmade.backend.history.repository.ScanConfigRepository;
import com.weldmade.backend.history.repository.ScanJobRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
@Transactional(readOnly = true)
public class ScanJobService {

    private final ScanJobRepository scanJobRepository;
    private final MeasurementRepository measurementRepository;
    private final ScanConfigRepository scanConfigRepository;

    public ScanJobService(
            ScanJobRepository scanJobRepository,
            MeasurementRepository measurementRepository,
            ScanConfigRepository scanConfigRepository
    ) {
        this.scanJobRepository = scanJobRepository;
        this.measurementRepository = measurementRepository;
        this.scanConfigRepository = scanConfigRepository;
    }

    public List<ScanJob> getScanJobs() {
        return scanJobRepository.findAllByOrderByCreatedAtDesc();
    }

    public Optional<ScanJob> getScanJob(String scanId) {
        return scanJobRepository.findById(scanId);
    }

    public Optional<ScanHistoryDetail> getScanHistoryDetail(String scanId) {
        return scanJobRepository.findById(scanId)
                .map(scanJob -> {
                    Measurement measurement =
                            measurementRepository.findById(scanId)
                                    .orElse(null);

                    ScanConfig scanConfig =
                            scanConfigRepository.findById(scanId)
                                    .orElse(null);

                    return new ScanHistoryDetail(
                            scanJob,
                            measurement,
                            scanConfig
                    );
                });
    }
}
