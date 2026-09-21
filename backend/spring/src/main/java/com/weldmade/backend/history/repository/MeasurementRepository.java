package com.weldmade.backend.history.repository;

import com.weldmade.backend.history.entity.Measurement;
import org.springframework.data.repository.Repository;

import java.util.Optional;

public interface MeasurementRepository extends Repository<Measurement, String> {

    Optional<Measurement> findById(String scanId);
}