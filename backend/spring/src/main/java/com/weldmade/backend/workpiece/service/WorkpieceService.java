package com.weldmade.backend.workpiece.service;

import com.weldmade.backend.workpiece.entity.Workpiece;
import com.weldmade.backend.workpiece.repository.WorkpieceRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
public class WorkpieceService {

    private final WorkpieceRepository workpieceRepository;

    public WorkpieceService(
            WorkpieceRepository workpieceRepository
    ) {
        this.workpieceRepository = workpieceRepository;
    }

    @Transactional(readOnly = true)
    public List<Workpiece> getWorkpieces() {
        return workpieceRepository.findAllByOrderByCreatedAtDesc();
    }

    @Transactional(readOnly = true)
    public Optional<Workpiece> getWorkpiece(String workpieceId) {
        return workpieceRepository.findById(workpieceId);
    }

    @Transactional
    public Workpiece createWorkpiece(
            String workpieceId,
            String name,
            String description
    ) {
        if (workpieceRepository.existsById(workpieceId)) {
            throw new IllegalArgumentException(
                    "Workpiece already exists: " + workpieceId
            );
        }

        Workpiece workpiece = new Workpiece(
                workpieceId,
                name,
                description
        );

        return workpieceRepository.save(workpiece);
    }

    @Transactional
    public Optional<Workpiece> updateWorkpiece(
            String workpieceId,
            String name,
            String description,
            boolean active
    ) {
        return workpieceRepository.findById(workpieceId)
                .map(workpiece -> {
                    workpiece.update(
                            name,
                            description,
                            active
                    );

                    return workpieceRepository.save(workpiece);
                });
    }
}