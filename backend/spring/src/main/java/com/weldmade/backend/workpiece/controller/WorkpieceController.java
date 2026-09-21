package com.weldmade.backend.workpiece.controller;

import com.weldmade.backend.workpiece.entity.Workpiece;
import com.weldmade.backend.workpiece.service.WorkpieceService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/workpieces")
public class WorkpieceController {

    private final WorkpieceService workpieceService;

    public WorkpieceController(
            WorkpieceService workpieceService
    ) {
        this.workpieceService = workpieceService;
    }

    @GetMapping
    public List<Workpiece> getWorkpieces() {
        return workpieceService.getWorkpieces();
    }

    @GetMapping("/{workpieceId}")
    public ResponseEntity<Workpiece> getWorkpiece(
            @PathVariable String workpieceId
    ) {
        return workpieceService.getWorkpiece(workpieceId)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<Workpiece> createWorkpiece(
            @RequestBody CreateWorkpieceRequest request
    ) {
        try {
            Workpiece workpiece = workpieceService.createWorkpiece(
                    request.workpieceId(),
                    request.name(),
                    request.description()
            );

            return ResponseEntity
                    .status(HttpStatus.CREATED)
                    .body(workpiece);

        } catch (IllegalArgumentException exception) {
            return ResponseEntity
                    .status(HttpStatus.CONFLICT)
                    .build();
        }
    }

    @PutMapping("/{workpieceId}")
    public ResponseEntity<Workpiece> updateWorkpiece(
            @PathVariable String workpieceId,
            @RequestBody UpdateWorkpieceRequest request
    ) {
        return workpieceService.updateWorkpiece(
                        workpieceId,
                        request.name(),
                        request.description(),
                        request.active()
                )
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    public record CreateWorkpieceRequest(
            String workpieceId,
            String name,
            String description
    ) {
    }

    public record UpdateWorkpieceRequest(
            String name,
            String description,
            boolean active
    ) {
    }
}