"""Batch processing engine.

Orchestrates processing of multiple RAW files through the pipeline,
tracking progress and supporting cancellation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable

from vedos.models import (
    BatchResult,
    PipelineResult,
    ProcessingConfig,
    ProcessingStatus,
)
from vedos.pipeline import process_file

logger = logging.getLogger(__name__)

ProgressEvent = dict[str, Any]


class BatchProcessor:
    """Orchestrates batch processing of multiple RAW files."""

    def __init__(self, config: ProcessingConfig, job_id: str):
        self.config = config
        self.job_id = job_id
        self.status = ProcessingStatus(
            job_id=job_id,
            status="queued",
            progress=0.0,
            total_files=len(config.files),
            completed_files=0,
        )
        self.cancel_requested = False
        self._progress_callbacks: list[Callable[[ProgressEvent], None]] = []
        self._results: list[PipelineResult] = []

    def on_progress(self, callback: Callable[[ProgressEvent], None]) -> None:
        """Register a progress callback."""
        self._progress_callbacks.append(callback)

    def _emit(self, event: ProgressEvent) -> None:
        for cb in self._progress_callbacks:
            try:
                cb(event)
            except Exception:
                logger.warning("Progress callback error", exc_info=True)

    async def process_all(self) -> BatchResult:
        """Process all files in the config."""
        start = time.monotonic()
        self.status.status = "processing"
        self._emit({"type": "started", "data": {"job_id": self.job_id, "total": len(self.config.files)}})

        output_dir = self.config.output_dir
        if not output_dir:
            # Default to sibling directory of first file
            output_dir = str(Path(self.config.files[0]).parent / "vedos_output") if self.config.files else "/tmp/vedos_output"
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        mask_region = None
        if self.config.mask_region:
            mr = self.config.mask_region
            mask_region = (mr.x, mr.y, mr.w, mr.h)

        inv_params = {}
        if self.config.inversion_params:
            inv_params = self.config.inversion_params.model_dump()

        for i, file_path in enumerate(self.config.files):
            if self.cancel_requested:
                self.status.status = "cancelled"
                self._emit({"type": "cancelled", "data": {"job_id": self.job_id}})
                break
            result = await self._process_single(
                file_path, i, output_dir, mask_region, inv_params
            )
            self._results.append(result)

        elapsed = time.monotonic() - start
        completed = sum(1 for r in self._results if r.error is None)
        failed = sum(1 for r in self._results if r.error is not None)

        if self.status.status != "cancelled":
            self.status.status = "complete" if failed == 0 else "complete"
        self.status.progress = 100.0
        self.status.completed_files = completed

        batch = BatchResult(
            job_id=self.job_id,
            total_files=len(self.config.files),
            completed=completed,
            failed=failed,
            results=self._results,
            total_time_seconds=round(elapsed, 3),
        )
        self._emit({"type": "complete", "data": batch.model_dump()})
        return batch

    async def _process_single(
        self,
        file_path: str,
        index: int,
        output_dir: str,
        mask_region: tuple[int, int, int, int] | None,
        inversion_params: dict,
    ) -> PipelineResult:
        """Process a single file through the full pipeline."""
        self.status.current_file = file_path
        total = max(len(self.config.files), 1)

        def file_progress(step: str, pct: float) -> None:
            overall = (index + pct) / total * 100.0
            self.status.progress = round(overall, 1)
            self._emit({
                "type": "progress",
                "data": {
                    "file": file_path,
                    "file_index": index,
                    "step": step,
                    "progress": pct,
                    "overall_progress": overall,
                },
            })

        result = await process_file(
            file_path=file_path,
            output_dir=output_dir,
            film_type=self.config.film_type.value,
            mask_region=mask_region,
            ai_correction=self.config.ai_correction,
            ai_model=self.config.ai_model.value,
            inversion_params=inversion_params,
            progress_callback=file_progress,
        )

        if result.error:
            self.status.errors.append(f"{file_path}: {result.error}")
            self._emit({"type": "error", "data": {"file": file_path, "error": result.error}})
        else:
            self.status.completed_files += 1

        # Yield control to event loop
        await asyncio.sleep(0)
        return result

    def cancel(self) -> None:
        """Request cancellation."""
        self.cancel_requested = True
