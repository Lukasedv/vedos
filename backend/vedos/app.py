"""FastAPI application and routes for Vedos."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from vedos import __version__
from vedos.batch_engine import BatchProcessor
from vedos.job_store import job_store
from vedos.models import (
    AICorrectionParams,
    AIModel,
    BatchResult,
    FileInfo,
    ProcessingConfig,
    ProcessingStatus,
)
from vedos.raw_reader import (
    get_raw_metadata,
    get_raw_thumbnail,
    get_supported_extensions,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Vedos", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (placeholder for real persistence)
_job_images: dict[str, np.ndarray] = {}
_job_corrected: dict[str, np.ndarray] = {}
_job_previews: dict[str, str] = {}

# Batch processing stores
_batch_processors: dict[str, BatchProcessor] = {}
_batch_results: dict[str, BatchResult] = {}
_batch_events: dict[str, asyncio.Queue] = {}


class AICorrectionRequest(BaseModel):
    job_id: str
    model: AIModel = AIModel.CLAUDE_SONNET


class AICorrectionResponse(BaseModel):
    corrections: AICorrectionParams
    preview_url: Optional[str] = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post("/api/import", response_model=list[FileInfo])
async def import_files(file_paths: list[str]) -> list[FileInfo]:
    """Accept file paths, validate they exist, and return metadata."""
    supported = get_supported_extensions()
    results: list[FileInfo] = []
    for fp in file_paths:
        p = Path(fp)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {fp}")
        stat = p.stat()

        width = 0
        height = 0
        camera_make = ""
        camera_model = ""

        if p.suffix.lower() in supported:
            try:
                meta = get_raw_metadata(fp)
                width = meta.width
                height = meta.height
                camera_make = meta.camera_make
                camera_model = meta.camera_model
            except Exception:
                logger.warning("Could not read metadata for %s", fp, exc_info=True)

        results.append(
            FileInfo(
                path=str(p.resolve()),
                filename=p.name,
                format=p.suffix.lstrip(".").upper(),
                width=width,
                height=height,
                file_size=stat.st_size,
                camera_make=camera_make,
                camera_model=camera_model,
            )
        )
    return results


@app.get("/api/thumbnail/{filename:path}")
async def get_thumbnail(filename: str, max_size: int = 400) -> Response:
    """Return the embedded JPEG thumbnail for a RAW file."""
    p = Path(filename)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    try:
        jpeg_bytes = get_raw_thumbnail(str(p), max_size=max_size)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Thumbnail extraction failed: {exc}")
    return Response(content=jpeg_bytes, media_type="image/jpeg")


@app.post("/api/process")
async def start_processing(config: ProcessingConfig) -> dict:
    """Accept processing config, create a BatchProcessor, and start background processing."""
    job_id = str(uuid.uuid4())
    processor = BatchProcessor(config, job_id)
    _batch_processors[job_id] = processor
    event_queue: asyncio.Queue = asyncio.Queue()
    _batch_events[job_id] = event_queue

    def _on_event(event: dict) -> None:
        try:
            event_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    processor.on_progress(_on_event)

    async def _run() -> None:
        try:
            result = await processor.process_all()
            _batch_results[job_id] = result
        except Exception as exc:
            logger.error("Batch job %s failed: %s", job_id, exc, exc_info=True)
            processor.status.status = "error"
            processor.status.errors.append(str(exc))

    asyncio.create_task(_run())
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/process/{job_id}/status", response_model=ProcessingStatus)
async def get_processing_status(job_id: str) -> ProcessingStatus:
    """Get processing status for a job."""
    processor = _batch_processors.get(job_id)
    if processor:
        return processor.status
    return ProcessingStatus(
        job_id=job_id,
        status="unknown",
        progress=0.0,
        total_files=0,
        completed_files=0,
    )


@app.post("/api/process/{job_id}/cancel")
async def cancel_processing(job_id: str) -> dict:
    """Request cancellation for a running job."""
    processor = _batch_processors.get(job_id)
    if not processor:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    processor.cancel()
    return {"job_id": job_id, "status": "cancel_requested"}


@app.get("/api/process/{job_id}/results", response_model=BatchResult)
async def get_processing_results(job_id: str) -> BatchResult:
    """Get results after batch processing completes."""
    result = _batch_results.get(job_id)
    if not result:
        processor = _batch_processors.get(job_id)
        if not processor:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        if processor.status.status in ("queued", "processing"):
            raise HTTPException(status_code=409, detail="Job still in progress")
        raise HTTPException(status_code=404, detail=f"No results for job: {job_id}")
    return result


@app.get("/api/process/{job_id}/stream")
async def stream_progress(job_id: str) -> StreamingResponse:
    """Server-Sent Events stream for real-time progress updates."""
    processor = _batch_processors.get(job_id)
    if not processor:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    queue = _batch_events.get(job_id)
    if not queue:
        raise HTTPException(status_code=404, detail=f"No event stream for job: {job_id}")

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("complete", "cancelled"):
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/ai-correct", response_model=AICorrectionResponse)
async def ai_correct(request: AICorrectionRequest) -> AICorrectionResponse:
    """Trigger AI color correction for a processed image.

    Accepts a JSON body with job_id and optional model selection.
    Loads the processed image, generates a JPEG preview, sends it to
    the AI for analysis, applies corrections, and returns the result.
    """
    from vedos.ai_correction import (
        CopilotColorAnalyzer,
        apply_corrections,
        generate_preview_jpeg,
    )

    image_data = _load_job_image(request.job_id)
    if image_data is None:
        raise HTTPException(status_code=404, detail=f"No image for job {request.job_id}")

    preview_path: str | None = None
    analyzer = CopilotColorAnalyzer(model=request.model.value)
    try:
        await analyzer.start()
        preview_path = generate_preview_jpeg(image_data)
        corrections = await analyzer.analyze_image(preview_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"AI analysis failed: {exc}"
        ) from exc
    finally:
        await analyzer.stop()
        if preview_path and os.path.exists(preview_path):
            os.unlink(preview_path)

    corrected = apply_corrections(image_data, corrections)
    _job_corrected[request.job_id] = corrected

    # Generate a preview of the corrected image
    corrected_preview = generate_preview_jpeg(corrected)
    _job_previews[request.job_id] = corrected_preview
    preview_url = f"/api/preview/{request.job_id}"

    return AICorrectionResponse(corrections=corrections, preview_url=preview_url)


@app.post("/api/ai-correct/refine", response_model=AICorrectionResponse)
async def ai_correct_refine(request: AICorrectionRequest) -> AICorrectionResponse:
    """Second-pass refinement: send the already-corrected image back to the AI.

    Returns additional delta corrections to apply on top of the first pass.
    """
    from vedos.ai_correction import (
        REFINE_PROMPT,
        CopilotColorAnalyzer,
        apply_corrections,
        generate_preview_jpeg,
    )

    corrected = _job_corrected.get(request.job_id)
    if corrected is None:
        raise HTTPException(
            status_code=404,
            detail=f"No corrected image for job {request.job_id}. Run /api/ai-correct first.",
        )

    preview_path: str | None = None
    analyzer = CopilotColorAnalyzer(model=request.model.value)
    try:
        await analyzer.start()
        preview_path = generate_preview_jpeg(corrected)
        delta = await analyzer.analyze_image(preview_path, prompt=REFINE_PROMPT)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"AI refinement failed: {exc}"
        ) from exc
    finally:
        await analyzer.stop()
        if preview_path and os.path.exists(preview_path):
            os.unlink(preview_path)

    refined = apply_corrections(corrected, delta)
    _job_corrected[request.job_id] = refined

    refined_preview = generate_preview_jpeg(refined)
    old_preview = _job_previews.get(request.job_id)
    if old_preview and os.path.exists(old_preview):
        os.unlink(old_preview)
    _job_previews[request.job_id] = refined_preview
    preview_url = f"/api/preview/{request.job_id}"

    return AICorrectionResponse(corrections=delta, preview_url=preview_url)


def _load_job_image(job_id: str) -> np.ndarray | None:
    """Load a processed image array for a given job ID from the in-memory store."""
    return _job_images.get(job_id)


@app.get("/api/preview/{job_id}")
async def get_preview(job_id: str) -> Response:
    """Serve the preview JPEG for a job."""
    preview_path = _job_previews.get(job_id)
    if not preview_path or not os.path.exists(preview_path):
        raise HTTPException(status_code=404, detail=f"No preview for job {job_id}")
    with open(preview_path, "rb") as f:
        jpeg_bytes = f.read()
    return Response(content=jpeg_bytes, media_type="image/jpeg")


def _generate_jpeg_bytes(image_data: np.ndarray) -> bytes:
    """Generate JPEG bytes from image data using generate_preview_jpeg."""
    from vedos.ai_correction import generate_preview_jpeg

    path = generate_preview_jpeg(image_data)
    try:
        with open(path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(path):
            os.unlink(path)


@app.get("/api/preview/{job_id}/{file_index}")
async def get_file_preview(job_id: str, file_index: int) -> Response:
    """Return a JPEG preview of the processed image for a specific file."""
    try:
        job = job_store.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Prefer corrected image, fall back to original
    image = job.corrected_images.get(file_index) or job.images.get(file_index)
    if image is None:
        raise HTTPException(
            status_code=404,
            detail=f"No image data for job {job_id} file {file_index}",
        )
    jpeg_bytes = _generate_jpeg_bytes(image)
    return Response(content=jpeg_bytes, media_type="image/jpeg")


@app.get("/api/preview/{job_id}/{file_index}/before")
async def get_file_preview_before(job_id: str, file_index: int) -> Response:
    """Return preview of the image before AI correction."""
    try:
        job = job_store.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    image = job.images.get(file_index)
    if image is None:
        raise HTTPException(
            status_code=404,
            detail=f"No original image for job {job_id} file {file_index}",
        )
    jpeg_bytes = _generate_jpeg_bytes(image)
    return Response(content=jpeg_bytes, media_type="image/jpeg")


@app.get("/api/preview/{job_id}/{file_index}/after")
async def get_file_preview_after(job_id: str, file_index: int) -> Response:
    """Return preview of the image after AI correction."""
    try:
        job = job_store.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    image = job.corrected_images.get(file_index)
    if image is None:
        raise HTTPException(
            status_code=404,
            detail=f"No corrected image for job {job_id} file {file_index}",
        )
    jpeg_bytes = _generate_jpeg_bytes(image)
    return Response(content=jpeg_bytes, media_type="image/jpeg")


class ManualCorrectionRequest(BaseModel):
    white_balance_shift: float = 0.0
    tint_shift: float = 0.0
    exposure_compensation: float = 0.0
    saturation_adjustment: float = 0.0


@app.post("/api/corrections/{job_id}/{file_index}")
async def apply_manual_corrections(
    job_id: str, file_index: int, request: ManualCorrectionRequest
) -> Response:
    """Apply manual correction overrides and return an updated preview."""
    from vedos.ai_correction import apply_corrections

    try:
        job = job_store.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    image = job.images.get(file_index)
    if image is None:
        raise HTTPException(
            status_code=404,
            detail=f"No image data for job {job_id} file {file_index}",
        )

    corrections = AICorrectionParams(
        white_balance_shift=request.white_balance_shift,
        tint_shift=request.tint_shift,
        exposure_compensation=request.exposure_compensation,
        saturation_adjustment=request.saturation_adjustment,
    )
    corrected = apply_corrections(image, corrections)
    job.corrected_images[file_index] = corrected

    jpeg_bytes = _generate_jpeg_bytes(corrected)
    return Response(content=jpeg_bytes, media_type="image/jpeg")


def main() -> None:
    parser = argparse.ArgumentParser(description="Vedos backend server")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()
    uvicorn.run("vedos.app:app", host=args.host, port=args.port, reload=True)


if __name__ == "__main__":
    main()
