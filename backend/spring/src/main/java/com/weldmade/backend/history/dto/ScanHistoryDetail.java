package com.weldmade.backend.history.dto;

import com.weldmade.backend.history.entity.Measurement;
import com.weldmade.backend.history.entity.ScanJob;

public class ScanHistoryDetail {

    private final ScanJob scanJob;
    private final Measurement measurement;

    public ScanHistoryDetail(
            ScanJob scanJob,
            Measurement measurement
    ) {
        this.scanJob = scanJob;
        this.measurement = measurement;
    }

    public ScanJob getScanJob() {
        return scanJob;
    }

    public Measurement getMeasurement() {
        return measurement;
    }
}