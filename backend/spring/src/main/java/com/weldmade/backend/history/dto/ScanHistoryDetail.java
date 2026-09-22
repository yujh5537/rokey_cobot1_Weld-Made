package com.weldmade.backend.history.dto;

import com.weldmade.backend.history.entity.Measurement;
import com.weldmade.backend.history.entity.ScanConfig;
import com.weldmade.backend.history.entity.ScanJob;

public class ScanHistoryDetail {

    private final ScanJob scanJob;
    private final Measurement measurement;
    private final ScanConfig scanConfig;

    public ScanHistoryDetail(
            ScanJob scanJob,
            Measurement measurement,
            ScanConfig scanConfig
    ) {
        this.scanJob = scanJob;
        this.measurement = measurement;
        this.scanConfig = scanConfig;
    }

    public ScanJob getScanJob() {
        return scanJob;
    }

    public Measurement getMeasurement() {
        return measurement;
    }

    public ScanConfig getScanConfig() {
        return scanConfig;
    }
}