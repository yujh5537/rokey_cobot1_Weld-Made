package com.weldmade.backend.history.repository;

import com.weldmade.backend.history.entity.ScanConfig;
import org.springframework.data.repository.Repository;

import java.util.Optional;

public interface ScanConfigRepository extends Repository<ScanConfig, String> {

    Optional<ScanConfig> findById(String scanId);
}
