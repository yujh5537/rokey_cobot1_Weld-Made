package com.weldmade.backend.history.service;

import com.weldmade.backend.history.dto.ScanHistoryDetail;
import com.weldmade.backend.history.entity.Measurement;
import com.weldmade.backend.history.entity.ScanConfig;
import com.weldmade.backend.history.entity.ScanJob;
import com.weldmade.backend.history.repository.MeasurementRepository;
import com.weldmade.backend.history.repository.ScanConfigRepository;
import com.weldmade.backend.history.repository.ScanJobRepository;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ScanJobServiceTest {

    @Test
    void getScanHistoryDetailIncludesScanConfig() {
        ScanJobRepository scanJobRepository = mock(ScanJobRepository.class);
        MeasurementRepository measurementRepository = mock(MeasurementRepository.class);
        ScanConfigRepository scanConfigRepository = mock(ScanConfigRepository.class);

        ScanJob scanJob = mock(ScanJob.class);
        Measurement measurement = mock(Measurement.class);
        ScanConfig scanConfig = mock(ScanConfig.class);

        String scanId = "test-scan-001";

        when(scanJobRepository.findById(scanId)).thenReturn(Optional.of(scanJob));
        when(measurementRepository.findById(scanId)).thenReturn(Optional.of(measurement));
        when(scanConfigRepository.findById(scanId)).thenReturn(Optional.of(scanConfig));

        ScanJobService service = new ScanJobService(
                scanJobRepository,
                measurementRepository,
                scanConfigRepository
        );

        ScanHistoryDetail detail = service.getScanHistoryDetail(scanId).orElseThrow();

        assertSame(scanJob, detail.getScanJob());
        assertSame(measurement, detail.getMeasurement());
        assertSame(scanConfig, detail.getScanConfig());
    }
}
