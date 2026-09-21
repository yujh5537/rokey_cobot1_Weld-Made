package com.weldmade.backend.history.repository;

import com.weldmade.backend.history.entity.ScanJob;
import org.springframework.data.repository.Repository;

import java.util.List;
import java.util.Optional;

public interface ScanJobRepository extends Repository<ScanJob, String> {

    List<ScanJob> findAllByOrderByCreatedAtDesc();

    Optional<ScanJob> findById(String scanId);
}