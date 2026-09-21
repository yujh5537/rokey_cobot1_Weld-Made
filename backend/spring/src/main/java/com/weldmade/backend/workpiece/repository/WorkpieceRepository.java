package com.weldmade.backend.workpiece.repository;

import com.weldmade.backend.workpiece.entity.Workpiece;
import org.springframework.data.repository.Repository;

import java.util.List;
import java.util.Optional;

public interface WorkpieceRepository extends Repository<Workpiece, String> {

    List<Workpiece> findAllByOrderByCreatedAtDesc();

    Optional<Workpiece> findById(String workpieceId);

    Workpiece save(Workpiece workpiece);

    boolean existsById(String workpieceId);
}